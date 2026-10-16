from datetime import timedelta

import pytest
from django.utils import timezone

from apps.identity.models import Role
from apps.opportunities.models import Opportunity

from .conftest import future, make_user, opportunity_payload

pytestmark = pytest.mark.django_db


def test_event_with_multiple_independent_slots(client_for, organizer, published_event,
                                               make_opportunity, anon):
    eid = published_event["id"]
    singer = make_opportunity(event_id=eid, title="Singer slot", capacity=8)
    host = make_opportunity(event_id=eid, title="Host", opportunity_type="host_role")
    r = anon.get(f"/api/v1/events/{eid}/opportunities/")
    assert {o["id"] for o in r.data} == {singer["id"], host["id"]}
    assert all(o["event"]["id"] == eid for o in r.data)


def test_standalone_opportunity_needs_no_event(make_opportunity, anon):
    opp = make_opportunity(opportunity_type="paid_gig", compensation_type="paid",
                           compensation_amount="5000.00", currency="inr")
    assert opp["event"] is None and opp["currency"] == "INR"
    r = anon.get(f"/api/v1/opportunities/{opp['id']}/")
    assert r.status_code == 200 and r.data["accepting_applications"] is True
    assert r.data["manager_stats"] is None  # never leak applicant counts publicly


def test_only_organizers_create_listings(client_for, artist, member):
    for user in (artist, member):
        r = client_for(user).post("/api/v1/opportunities/", opportunity_payload(), format="json")
        assert r.status_code == 403 and r.data["error"]["code"] == "role_required"


def test_incomplete_listing_cannot_be_published(client_for, organizer):
    c = client_for(organizer)
    opp = c.post("/api/v1/opportunities/", opportunity_payload(location_text=""),
                 format="json").data
    r = c.post(f"/api/v1/opportunities/{opp['id']}/publish/")
    assert r.status_code == 400 and r.data["error"]["code"] == "listing_incomplete"
    event = c.post("/api/v1/events/", {"title": "No date"}, format="json").data
    r = c.post(f"/api/v1/events/{event['id']}/publish/")
    assert r.status_code == 400 and "starts_at" in r.data["error"]["details"]["fields"]


def test_slot_under_draft_event_cannot_publish(client_for, organizer):
    c = client_for(organizer)
    event = c.post("/api/v1/events/", {"title": "Draft fest", "starts_at": future(3),
                                       "location_text": "Pune"}, format="json").data
    opp = c.post("/api/v1/opportunities/", opportunity_payload(event_id=event["id"]),
                 format="json").data
    r = c.post(f"/api/v1/opportunities/{opp['id']}/publish/")
    assert r.status_code == 409 and r.data["error"]["code"] == "event_not_published"


def test_other_organizers_cannot_see_drafts_or_modify_listings(client_for, organizer2,
                                                                make_opportunity, anon):
    draft = make_opportunity(publish=False)
    live = make_opportunity()
    other = client_for(organizer2)
    assert other.get(f"/api/v1/opportunities/{draft['id']}/").status_code == 404
    assert anon.get(f"/api/v1/opportunities/{draft['id']}/").status_code == 404
    assert other.patch(f"/api/v1/opportunities/{live['id']}/", {"description": "x"},
                       format="json").status_code == 403
    assert other.post(f"/api/v1/opportunities/{live['id']}/cancel/").status_code == 403
    assert other.post(f"/api/v1/opportunities/{draft['id']}/publish/").status_code == 404


def test_cannot_attach_slot_to_someone_elses_event(client_for, organizer2, published_event):
    r = client_for(organizer2).post(
        "/api/v1/opportunities/", opportunity_payload(event_id=published_event["id"]),
        format="json",
    )
    assert r.status_code == 403


def test_published_listing_locks_core_terms(client_for, organizer, make_opportunity):
    opp = make_opportunity()
    r = client_for(organizer).patch(f"/api/v1/opportunities/{opp['id']}/",
                                    {"compensation_type": "paid"}, format="json")
    assert r.status_code == 409 and r.data["error"]["code"] == "field_locked"
    r = client_for(organizer).patch(f"/api/v1/opportunities/{opp['id']}/",
                                    {"description": "Updated"}, format="json")
    assert r.status_code == 200 and r.data["description"] == "Updated"


def test_discovery_filters_and_hides_expired(client_for, organizer, make_opportunity, anon):
    jazz = make_opportunity(title="Jazz night", genres=["jazz"], location_text="Mumbai",
                            opportunity_type="band_slot")
    make_opportunity(title="Rock night", genres=["rock"], location_text="Delhi")
    expired = make_opportunity(title="Old", application_deadline=future(1))
    Opportunity.objects.filter(id=expired["id"]).update(
        application_deadline=timezone.now() - timedelta(hours=1)
    )
    ids = lambda r: [o["id"] for o in r.data["results"]]  # noqa: E731
    assert ids(anon.get("/api/v1/opportunities/?genre=jazz")) == [jazz["id"]]
    assert ids(anon.get("/api/v1/opportunities/?location=mumbai")) == [jazz["id"]]
    assert ids(anon.get("/api/v1/opportunities/?type=band_slot")) == [jazz["id"]]
    assert expired["id"] not in ids(anon.get("/api/v1/opportunities/"))
    assert anon.get("/api/v1/opportunities/?type=bogus").status_code == 400


def test_venue_manager_can_manage_events_at_their_venue(client_for, organizer, organizer2):
    venue = client_for(organizer).post("/api/v1/venues/", {"name": "Blue Room", "city": "Goa"},
                                       format="json").data
    # Not a manager -> may not attach events to the venue.
    r = client_for(organizer2).post("/api/v1/events/", {"title": "Gig", "venue_id": venue["id"]},
                                    format="json")
    assert r.status_code == 403
    event = client_for(organizer).post("/api/v1/events/", {
        "title": "Gig", "venue_id": venue["id"], "starts_at": future(4)}, format="json").data
    assert client_for(organizer2).post(f"/api/v1/events/{event['id']}/publish/").status_code == 404
    # Explicit assignment grants management.
    r = client_for(organizer).post(f"/api/v1/venues/{venue['id']}/managers/",
                                   {"user_id": str(organizer2.id)}, format="json")
    assert r.status_code == 204
    assert client_for(organizer2).post(f"/api/v1/events/{event['id']}/publish/").status_code == 200


def test_event_cancellation_requires_confirmation_and_does_not_cascade(
    client_for, organizer, artist, published_event, make_opportunity, apply, run_outbox
):
    from apps.notifications.models import Notification

    slot = make_opportunity(event_id=published_event["id"])
    app = apply(artist, slot["id"]).data
    client_for(organizer).post(f"/api/v1/applications/{app['id']}/accept/")
    url = f"/api/v1/events/{published_event['id']}/cancel/"
    r = client_for(organizer).post(url, {"reason": "Venue flooded"}, format="json")
    assert r.status_code == 409 and r.data["error"]["code"] == "confirmation_required"
    r = client_for(organizer).post(url, {"reason": "Venue flooded", "confirm": True},
                                   format="json")
    assert r.status_code == 200 and r.data["event"]["status"] == "cancelled"
    # Manual review: the slot is still live and listed as awaiting a decision...
    assert [o["id"] for o in r.data["opportunities_awaiting_review"]] == [slot["id"]]
    # ...but it no longer accepts applications.
    artist3 = make_user("a3@example.com", Role.ARTIST)
    assert apply(artist3, slot["id"]).status_code == 409
    run_outbox()
    assert Notification.objects.filter(recipient=artist,
                                       notification_type="event.cancelled").exists()


def test_event_timezone_must_be_iana(client_for, organizer):
    r = client_for(organizer).post("/api/v1/events/", {"title": "X", "timezone": "Mars/Base"},
                                   format="json")
    assert r.status_code == 400

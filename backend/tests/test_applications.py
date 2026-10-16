from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.notifications.models import Notification
from apps.opportunities.models import Application, Booking, Opportunity

pytestmark = pytest.mark.django_db


def act(client, application_id, action, **body):
    return client.post(f"/api/v1/applications/{application_id}/{action}/", body, format="json")


def test_journey_apply_review_accept_book_complete(client_for, organizer, artist, make_opportunity,
                                                    apply, run_outbox):
    portfolio = client_for(artist).post("/api/v1/profiles/me/portfolio/", {
        "title": "Live at Hard Rock", "url": "https://youtube.com/watch?v=x"}, format="json").data
    opp = make_opportunity(capacity=2)
    r = apply(artist, opp["id"], cover_note="Hi!", portfolio_item_ids=[portfolio["id"]])
    assert r.status_code == 201 and r.data["status"] == "submitted"
    app_id = r.data["id"]
    run_outbox()
    assert Notification.objects.filter(recipient=organizer,
                                       notification_type="application.submitted").count() == 1

    org = client_for(organizer)
    listing = org.get(f"/api/v1/opportunities/{opp['id']}/applications/").data["results"]
    assert listing[0]["portfolio_items"][0]["title"] == "Live at Hard Rock"
    assert act(org, app_id, "shortlist").data["status"] == "shortlisted"
    accepted = act(org, app_id, "accept", reason="Great fit")
    assert accepted.status_code == 200
    assert accepted.data["status"] == "accepted"
    assert accepted.data["booking"]["status"] == "confirmed"  # acceptance confirms the booking

    run_outbox()
    kinds = set(Notification.objects.filter(recipient=artist)
                .values_list("notification_type", flat=True))
    assert {"application.shortlisted", "application.accepted"} <= kinds

    mine = client_for(artist).get("/api/v1/applications/mine/").data["results"]
    assert mine[0]["status"] == "accepted"
    history = client_for(artist).get(f"/api/v1/applications/{app_id}/history/").data
    assert [h["to_status"] for h in history] == ["submitted", "shortlisted", "accepted"]
    assert history[-1]["reason"] == "Great fit" and history[-1]["actor"]["id"] == str(organizer.id)

    booking_id = accepted.data["booking"]["id"]
    assert client_for(artist).post(f"/api/v1/bookings/{booking_id}/complete/").status_code == 403
    done = org.post(f"/api/v1/bookings/{booking_id}/complete/")
    assert done.status_code == 200 and done.data["status"] == "completed"
    assert AuditEvent.objects.filter(action="application.accepted").exists()


def test_apply_rules(client_for, organizer, artist, member, make_opportunity, apply):
    opp = make_opportunity()
    assert apply(member, opp["id"]).status_code == 403  # needs artist capability
    assert apply(artist, opp["id"]).status_code == 201
    dup = apply(artist, opp["id"])
    assert dup.status_code == 409 and dup.data["error"]["code"] == "already_applied"

    closed = make_opportunity()
    client_for(organizer).post(f"/api/v1/opportunities/{closed['id']}/close/")
    r = apply(artist, closed["id"])
    assert r.status_code == 409 and r.data["error"]["code"] == "application_not_open"

    expired = make_opportunity()
    Opportunity.objects.filter(id=expired["id"]).update(
        application_deadline=timezone.now() - timedelta(minutes=1))
    assert apply(artist, expired["id"]).status_code == 409

    draft = make_opportunity(publish=False)
    assert apply(artist, draft["id"]).status_code == 404

    bogus = client_for(artist).post(
        f"/api/v1/opportunities/{opp['id']}/applications/",
        {"portfolio_item_ids": ["00000000-0000-0000-0000-000000000000"]}, format="json")
    assert bogus.status_code == 400


def test_cannot_apply_to_own_listing(client_for, organizer, make_opportunity, apply):
    client_for(organizer).post("/api/v1/auth/me/roles/", {"role": "artist"}, format="json")
    opp = make_opportunity()
    r = apply(organizer, opp["id"])
    assert r.status_code == 409 and r.data["error"]["code"] == "own_opportunity"


def test_applicants_cannot_see_each_other(client_for, artist, artist2, make_opportunity, apply):
    opp = make_opportunity()
    mine = apply(artist, opp["id"]).data
    apply(artist2, opp["id"])
    other = client_for(artist2)
    assert other.get(f"/api/v1/applications/{mine['id']}/").status_code == 404
    assert other.get(f"/api/v1/opportunities/{opp['id']}/applications/").status_code == 403
    assert len(other.get("/api/v1/applications/mine/").data["results"]) == 1


def test_other_organizer_cannot_review_or_decide(client_for, organizer2, artist,
                                                 make_opportunity, apply):
    opp = make_opportunity()
    app = apply(artist, opp["id"]).data
    other = client_for(organizer2)
    assert other.get(f"/api/v1/opportunities/{opp['id']}/applications/").status_code == 403
    assert act(other, app["id"], "accept").status_code == 404
    assert Application.objects.get(id=app["id"]).status == "submitted"


def test_invalid_and_stale_transitions_are_rejected(client_for, organizer, artist,
                                                    make_opportunity, apply):
    org = client_for(organizer)
    opp = make_opportunity()
    app = apply(artist, opp["id"]).data
    assert act(client_for(artist), app["id"], "accept").status_code == 403
    assert act(org, app["id"], "withdraw").status_code == 403
    assert act(org, app["id"], "decline").status_code == 200
    r = act(org, app["id"], "accept")
    assert r.status_code == 409 and r.data["error"]["code"] == "invalid_transition"
    r = act(client_for(artist), app["id"], "withdraw")
    assert r.status_code == 409  # final states are never silently overwritten


def test_repeated_accept_is_idempotent(client_for, organizer, artist, make_opportunity, apply,
                                       run_outbox):
    opp = make_opportunity()
    app = apply(artist, opp["id"]).data
    org = client_for(organizer)
    assert act(org, app["id"], "accept").status_code == 200
    assert act(org, app["id"], "accept").status_code == 200  # client retry
    assert Booking.objects.filter(application_id=app["id"]).count() == 1
    run_outbox()
    assert Notification.objects.filter(recipient=artist,
                                       notification_type="application.accepted").count() == 1


def test_capacity_is_enforced_and_freed_by_booking_cancellation(
    client_for, organizer, artist, artist2, make_opportunity, apply, run_outbox
):
    opp = make_opportunity(capacity=1)
    a1 = apply(artist, opp["id"]).data
    a2 = apply(artist2, opp["id"]).data
    org = client_for(organizer)
    booking = act(org, a1["id"], "accept").data["booking"]
    full = act(org, a2["id"], "accept")
    assert full.status_code == 409 and full.data["error"]["code"] == "capacity_full"
    # The performer drops out -> organizer is notified and the seat is released.
    r = client_for(artist).post(f"/api/v1/bookings/{booking['id']}/cancel/",
                                {"reason": "Sick"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "cancelled"
    assert Application.objects.get(id=a1["id"]).status == "accepted"  # decision is history
    assert act(org, a2["id"], "accept").status_code == 200
    run_outbox()
    assert Notification.objects.filter(recipient=organizer,
                                       notification_type="booking.cancelled").exists()


def test_capacity_cannot_drop_below_confirmed_bookings(client_for, organizer, artist,
                                                       make_opportunity, apply):
    opp = make_opportunity(capacity=2)
    app = apply(artist, opp["id"]).data
    act(client_for(organizer), app["id"], "accept")
    r = client_for(organizer).patch(f"/api/v1/opportunities/{opp['id']}/", {"capacity": 0},
                                    format="json")
    assert r.status_code == 400  # serializer min_value
    opp2 = make_opportunity(capacity=1)
    app2 = apply(artist, opp2["id"]).data
    act(client_for(organizer), app2["id"], "accept")
    assert client_for(organizer).patch(f"/api/v1/opportunities/{opp2['id']}/", {"capacity": 1},
                                       format="json").status_code == 200


def test_withdrawal_rules(client_for, organizer, artist, make_opportunity, apply, run_outbox):
    opp = make_opportunity(capacity=3)
    app = apply(artist, opp["id"]).data
    assert act(client_for(artist), app["id"], "withdraw").data["status"] == "withdrawn"
    run_outbox()
    assert Notification.objects.filter(recipient=organizer,
                                       notification_type="application.withdrawn").exists()
    opp2 = make_opportunity()
    app2 = apply(artist, opp2["id"]).data
    act(client_for(organizer), app2["id"], "accept")
    r = act(client_for(artist), app2["id"], "withdraw")
    assert r.status_code == 409  # after acceptance, cancel the booking instead


def test_opportunity_cancellation_cancels_bookings_and_notifies(
    client_for, organizer, artist, artist2, make_opportunity, apply, run_outbox
):
    opp = make_opportunity(capacity=2)
    a1 = apply(artist, opp["id"]).data
    apply(artist2, opp["id"])
    org = client_for(organizer)
    act(org, a1["id"], "accept")
    url = f"/api/v1/opportunities/{opp['id']}/cancel/"
    assert org.post(url, {}, format="json").data["error"]["code"] == "confirmation_required"
    r = org.post(url, {"confirm": True, "reason": "Budget cut"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "cancelled"
    assert Booking.objects.get(application_id=a1["id"]).status == "cancelled"
    run_outbox()
    for user in (artist, artist2):
        assert Notification.objects.filter(recipient=user,
                                           notification_type="opportunity.cancelled").exists()


def test_lineup_and_manager_stats(client_for, organizer, organizer2, artist, published_event,
                                  make_opportunity, apply):
    slot = make_opportunity(event_id=published_event["id"])
    app = apply(artist, slot["id"]).data
    act(client_for(organizer), app["id"], "accept")
    lineup = client_for(organizer).get(f"/api/v1/events/{published_event['id']}/lineup/")
    assert [b["performer"]["id"] for b in lineup.data] == [str(artist.id)]
    assert client_for(organizer2).get(
        f"/api/v1/events/{published_event['id']}/lineup/").status_code == 403
    stats = client_for(organizer).get(f"/api/v1/opportunities/{slot['id']}/").data["manager_stats"]
    assert stats["applications"]["accepted"] == 1 and stats["confirmed_bookings"] == 1


def test_funnel_metrics_admin_only(client_for, organizer, admin_user, artist, make_opportunity,
                                   apply):
    opp = make_opportunity()
    app = apply(artist, opp["id"]).data
    booking = act(client_for(organizer), app["id"], "accept").data["booking"]
    client_for(organizer).post(f"/api/v1/bookings/{booking['id']}/complete/")
    assert client_for(organizer).get("/api/v1/metrics/funnel/").status_code == 403
    month = client_for(admin_user).get("/api/v1/metrics/funnel/").data["months"][-1]
    assert month["listings_published"] == 1 and month["applications_submitted"] == 1
    assert month["performances_completed"] == 1 and month["successful_connections"] == 1

import pytest
from django.db import transaction

from apps.outbox import services as outbox
from apps.outbox.models import OutboxEvent

pytestmark = pytest.mark.django_db


def test_profile_editing_and_role_gated_details(client_for, artist, member):
    a = client_for(artist)
    r = a.patch("/api/v1/profiles/me/", {
        "bio": "Indie singer-songwriter", "location_label": "Bengaluru",
        "artist": {"artist_name": "Asha", "genres": ["indie", "folk"], "skills": ["singing"]},
    }, format="json")
    assert r.status_code == 200
    assert r.data["artist"]["genres"] == ["folk", "indie"] or set(r.data["artist"]["genres"]) == {
        "indie", "folk"}
    bad = a.patch("/api/v1/profiles/me/", {"artist": {"genres": ["polka-metal"]}}, format="json")
    assert bad.status_code == 400
    r = client_for(member).patch("/api/v1/profiles/me/", {"artist": {"artist_name": "X"}},
                                 format="json")
    assert r.status_code == 403 and r.data["error"]["code"] == "role_required"
    assert a.patch("/api/v1/profiles/me/", {"user_id": "x", "visibility": "nope"},
                   format="json").status_code == 400


def test_profile_visibility(client_for, artist, member, anon):
    pid = str(artist.profile.id)
    client_for(artist).patch("/api/v1/profiles/me/", {"visibility": "members"}, format="json")
    assert anon.get(f"/api/v1/profiles/{pid}/").status_code == 404
    assert client_for(member).get(f"/api/v1/profiles/{pid}/").status_code == 200
    client_for(artist).patch("/api/v1/profiles/me/", {"visibility": "private"}, format="json")
    assert client_for(member).get(f"/api/v1/profiles/{pid}/").status_code == 404
    assert client_for(artist).get(f"/api/v1/profiles/{pid}/").status_code == 200


def test_artist_discovery_by_genre(client_for, artist, artist2, anon):
    client_for(artist).patch("/api/v1/profiles/me/", {"artist": {"genres": ["jazz"]}},
                             format="json")
    client_for(artist2).patch("/api/v1/profiles/me/", {"artist": {"genres": ["rock"]}},
                              format="json")
    r = anon.get("/api/v1/profiles/?genre=jazz&role=artist")
    assert [p["user_id"] for p in r.data["results"]] == [str(artist.id)]


def test_portfolio_items_are_owner_scoped(client_for, artist, artist2):
    item = client_for(artist).post("/api/v1/profiles/me/portfolio/", {
        "title": "Demo", "url": "https://soundcloud.com/x", "item_type": "audio"},
        format="json").data
    assert client_for(artist2).delete(f"/api/v1/profiles/me/portfolio/{item['id']}/").status_code \
        == 404
    bad = client_for(artist).post("/api/v1/profiles/me/portfolio/", {
        "title": "XSS", "url": "javascript:alert(1)"}, format="json")
    assert bad.status_code == 400


def test_notifications_are_private_and_markable(client_for, artist, member, run_outbox):
    client_for(member).post(f"/api/v1/users/{artist.id}/follow/")
    run_outbox()
    a = client_for(artist)
    notes = a.get("/api/v1/notifications/").data["results"]
    assert len(notes) == 1 and notes[0]["actor"]["id"] == str(member.id)
    assert client_for(member).post(
        f"/api/v1/notifications/{notes[0]['id']}/read/").status_code == 404
    assert a.get("/api/v1/notifications/unread-count/").data == {"unread": 1}
    assert a.post(f"/api/v1/notifications/{notes[0]['id']}/read/").data["is_read"] is True
    assert a.get("/api/v1/notifications/?unread=true").data["results"] == []


@pytest.mark.django_db(transaction=True)
def test_outbox_publish_outside_transaction_is_a_bug():
    # Publishing outside the business transaction could record an event for a change that
    # later rolls back (or lose one that commits), which is exactly what the outbox prevents.
    with pytest.raises(RuntimeError):
        outbox.publish("test.event", {})


def test_outbox_isolates_failing_handlers(run_outbox):
    calls = []

    def boom(payload):
        raise ValueError("handler bug")

    outbox.subscribe("test.fails", boom)
    outbox.subscribe("test.works", calls.append)
    with transaction.atomic():
        bad = outbox.publish("test.fails", {"n": 1})
        good = outbox.publish("test.works", {"n": 2})
    assert run_outbox() == 2
    bad.refresh_from_db()
    good.refresh_from_db()
    assert good.processed_at is not None and calls == [{"n": 2}]
    assert bad.processed_at is None and bad.attempts == 1 and "handler bug" in bad.last_error
    run_outbox()
    assert calls == [{"n": 2}]  # processed events are never redelivered
    assert OutboxEvent.objects.get(pk=bad.pk).attempts == 2  # failures are retried later

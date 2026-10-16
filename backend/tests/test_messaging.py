import pytest

from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def start(client, user):
    return client.post("/api/v1/conversations/", {"user_id": str(user.id)}, format="json")


def test_direct_messaging_flow_with_unread_state(client_for, artist, organizer, run_outbox):
    o, a = client_for(organizer), client_for(artist)
    conv = start(o, artist)
    assert conv.status_code == 201
    assert start(a, organizer).data["id"] == conv.data["id"]  # same pair -> same conversation
    cid = conv.data["id"]
    r = o.post(f"/api/v1/conversations/{cid}/messages/", {"body": "Can you play Friday?"},
               format="json")
    assert r.status_code == 201
    o.post(f"/api/v1/conversations/{cid}/messages/", {"body": "8pm slot"}, format="json")

    inbox = a.get("/api/v1/conversations/").data["results"]
    assert inbox[0]["unread_count"] == 2 and inbox[0]["last_message"]["preview"] == "8pm slot"
    assert o.get("/api/v1/conversations/").data["results"][0]["unread_count"] == 0
    assert a.get("/api/v1/conversations/unread-count/").data == {"unread": 2}

    run_outbox()
    notes = Notification.objects.filter(recipient=artist, notification_type="message.received")
    assert notes.count() == 1  # one entry per conversation, not per message
    assert notes.get().payload == {}  # message bodies never copied into notifications

    msgs = a.get(f"/api/v1/conversations/{cid}/messages/").data["results"]
    assert [m["body"] for m in msgs] == ["8pm slot", "Can you play Friday?"]
    assert a.post(f"/api/v1/conversations/{cid}/read/").status_code == 204
    assert a.get("/api/v1/conversations/").data["results"][0]["unread_count"] == 0
    assert notes.get().read_at is not None


def test_non_participants_cannot_read_or_send(client_for, artist, organizer, member):
    cid = start(client_for(organizer), artist).data["id"]
    msg = client_for(organizer).post(f"/api/v1/conversations/{cid}/messages/", {"body": "hi"},
                                     format="json").data
    intruder = client_for(member)
    assert intruder.get(f"/api/v1/conversations/{cid}/").status_code == 404
    assert intruder.get(f"/api/v1/conversations/{cid}/messages/").status_code == 404
    assert intruder.post(f"/api/v1/conversations/{cid}/messages/", {"body": "x"},
                         format="json").status_code == 404
    assert intruder.delete(f"/api/v1/messages/{msg['id']}/").status_code == 404
    # Reporting cannot be used to probe a private message either.
    r = intruder.post("/api/v1/reports/", {"target_type": "message", "target_id": msg["id"],
                                           "reason_code": "spam"}, format="json")
    assert r.status_code == 404


def test_sender_can_delete_own_message_only(client_for, artist, organizer):
    cid = start(client_for(organizer), artist).data["id"]
    msg = client_for(organizer).post(f"/api/v1/conversations/{cid}/messages/", {"body": "oops"},
                                     format="json").data
    assert client_for(artist).delete(f"/api/v1/messages/{msg['id']}/").status_code == 403
    assert client_for(organizer).delete(f"/api/v1/messages/{msg['id']}/").status_code == 204
    shown = client_for(artist).get(f"/api/v1/conversations/{cid}/messages/").data["results"][0]
    assert shown["body"] is None and shown["is_deleted"] is True


def test_cannot_message_self_or_send_empty(client_for, artist, organizer):
    assert start(client_for(artist), artist).status_code == 400
    cid = start(client_for(organizer), artist).data["id"]
    assert client_for(organizer).post(f"/api/v1/conversations/{cid}/messages/", {"body": "  "},
                                      format="json").status_code == 400


def test_archive_and_new_message_unarchives(client_for, artist, organizer):
    cid = start(client_for(organizer), artist).data["id"]
    a = client_for(artist)
    a.post(f"/api/v1/conversations/{cid}/archive/", {"archived": True}, format="json")
    assert a.get("/api/v1/conversations/").data["results"] == []
    assert len(a.get("/api/v1/conversations/?archived=true").data["results"]) == 1
    client_for(organizer).post(f"/api/v1/conversations/{cid}/messages/", {"body": "ping"},
                               format="json")
    assert len(a.get("/api/v1/conversations/").data["results"]) == 1

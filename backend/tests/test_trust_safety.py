import pytest

from apps.audit.models import AuditEvent
from apps.notifications.models import Notification
from apps.social.models import Follow

pytestmark = pytest.mark.django_db


def block(client, user):
    return client.post("/api/v1/blocks/", {"user_id": str(user.id)}, format="json")


def test_block_prevents_interaction_across_domains(client_for, artist, member, organizer,
                                                   make_opportunity, apply, run_outbox):
    a, m = client_for(artist), client_for(member)
    m.post(f"/api/v1/users/{artist.id}/follow/")
    a.post(f"/api/v1/users/{member.id}/follow/")
    p = a.post("/api/v1/posts/", {"body": "hi"}, format="json").data
    cid = m.post("/api/v1/conversations/", {"user_id": str(artist.id)}, format="json").data["id"]

    assert block(a, member).status_code == 201
    assert block(a, member).status_code == 200  # idempotent
    assert not Follow.objects.filter(follower__in=[artist, member],
                                     followed__in=[artist, member]).exists()
    # Blocked user loses access to the blocker's content and interactions...
    assert m.get(f"/api/v1/posts/{p['id']}/").status_code == 404
    assert m.post(f"/api/v1/posts/{p['id']}/like/").status_code == 404
    assert m.post(f"/api/v1/users/{artist.id}/follow/").status_code == 404
    assert m.get(f"/api/v1/profiles/{artist.profile.id}/").status_code == 404
    r = m.post(f"/api/v1/conversations/{cid}/messages/", {"body": "hey"}, format="json")
    assert r.status_code == 403 and r.data["error"]["code"] == "blocked"
    # ...and the blocker cannot message them either (symmetric).
    assert a.post("/api/v1/conversations/", {"user_id": str(member.id)},
                  format="json").status_code == 403
    # Blocks also suppress notifications that are already queued.
    assert client_for(artist).delete(f"/api/v1/blocks/{member.id}/").status_code == 204
    m.post(f"/api/v1/posts/{p['id']}/like/")
    block(a, member)
    run_outbox()
    assert not Notification.objects.filter(recipient=artist, actor=member,
                                           notification_type="post.liked").exists()


def test_report_is_idempotent_and_private_to_reporter(client_for, artist, member):
    p = client_for(artist).post("/api/v1/posts/", {"body": "spam spam"}, format="json").data
    body = {"target_type": "post", "target_id": p["id"], "reason_code": "spam"}
    r1 = client_for(member).post("/api/v1/reports/", body, format="json")
    r2 = client_for(member).post("/api/v1/reports/", body, format="json")
    assert r1.status_code == 201 and r2.status_code == 200 and r1.data["id"] == r2.data["id"]
    assert client_for(artist).get("/api/v1/reports/").data["results"] == []
    missing = {"target_type": "post", "target_id": "00000000-0000-0000-0000-000000000000",
               "reason_code": "spam"}
    assert client_for(member).post("/api/v1/reports/", missing, format="json").status_code == 404


def test_moderation_is_restricted_and_audited(client_for, artist, member, moderator, admin_user):
    p = client_for(artist).post("/api/v1/posts/", {"body": "abuse"}, format="json").data
    report = client_for(member).post("/api/v1/reports/", {
        "target_type": "post", "target_id": p["id"], "reason_code": "harassment"},
        format="json").data
    for user in (artist, member):
        assert client_for(user).get("/api/v1/moderation/reports/").status_code == 403

    mod = client_for(moderator)
    queue = mod.get("/api/v1/moderation/reports/?status=open").data["results"]
    assert [r["id"] for r in queue] == [report["id"]]
    detail = mod.get(f"/api/v1/moderation/reports/{report['id']}/").data
    assert detail["target"]["body"] == "abuse"
    r = mod.post(f"/api/v1/moderation/reports/{report['id']}/actions/",
                 {"action_type": "hide_content", "reason_code": "harassment"}, format="json")
    assert r.status_code == 201
    assert client_for(member).get(f"/api/v1/posts/{p['id']}/").status_code == 404
    assert client_for(artist).patch(f"/api/v1/posts/{p['id']}/", {"body": "x"},
                                    format="json").status_code == 409
    again = mod.post(f"/api/v1/moderation/reports/{report['id']}/actions/",
                     {"action_type": "dismiss", "reason_code": "x"}, format="json")
    assert again.status_code == 409
    assert AuditEvent.objects.filter(action="moderation.hide_content", actor=moderator).exists()


def test_only_admins_suspend_accounts(client_for, artist, member, moderator, admin_user):
    report = client_for(member).post("/api/v1/reports/", {
        "target_type": "user", "target_id": str(artist.id), "reason_code": "scam"},
        format="json").data
    url = f"/api/v1/moderation/reports/{report['id']}/actions/"
    body = {"action_type": "suspend_user", "reason_code": "scam"}
    assert client_for(moderator).post(url, body, format="json").status_code == 403
    assert client_for(admin_user).post(url, body, format="json").status_code == 201
    artist.refresh_from_db()
    assert artist.account_status == "suspended" and not artist.is_active


def test_message_reports_audit_moderator_access(client_for, artist, organizer, moderator):
    cid = client_for(organizer).post("/api/v1/conversations/", {"user_id": str(artist.id)},
                                     format="json").data["id"]
    msg = client_for(organizer).post(f"/api/v1/conversations/{cid}/messages/",
                                     {"body": "send me your bank details"}, format="json").data
    report = client_for(artist).post("/api/v1/reports/", {
        "target_type": "message", "target_id": msg["id"], "reason_code": "scam"},
        format="json").data
    client_for(moderator).get(f"/api/v1/moderation/reports/{report['id']}/")
    assert AuditEvent.objects.filter(action="moderation.message_viewed", actor=moderator).exists()


def test_moderator_can_close_misleading_listing(client_for, member, moderator, make_opportunity):
    opp = make_opportunity()
    report = client_for(member).post("/api/v1/reports/", {
        "target_type": "opportunity", "target_id": opp["id"],
        "reason_code": "misleading_listing"}, format="json").data
    client_for(moderator).post(f"/api/v1/moderation/reports/{report['id']}/actions/",
                               {"action_type": "close_listing", "reason_code": "misleading"},
                               format="json")
    assert client_for(member).get(f"/api/v1/opportunities/{opp['id']}/").data["status"] == "closed"

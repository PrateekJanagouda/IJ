import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.identity.models import AccountStatus
from apps.identity.services import set_account_status

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def register(client, **overrides):
    body = {"email": "New@Example.com", "password": PASSWORD, "display_name": "Newbie",
            "roles": ["artist", "organizer"]}
    body.update(overrides)
    return client.post("/api/v1/auth/register/", body, format="json")


def test_register_creates_logged_in_multi_role_account_with_profile(anon):
    r = register(anon)
    assert r.status_code == 201
    assert r.data["email"] == "new@example.com"  # normalized
    assert r.data["roles"] == ["artist", "organizer"]
    assert r.data["profile_id"]
    me = anon.get("/api/v1/auth/me/")
    assert me.status_code == 200 and me.data["display_name"] == "Newbie"


def test_register_rejects_duplicate_email_and_weak_password(anon):
    assert register(anon).status_code == 201
    dup = register(APIClient(), email="new@EXAMPLE.com")
    assert dup.status_code == 409 and dup.data["error"]["code"] == "email_taken"
    weak = register(APIClient(), email="weak@example.com", password="123")
    assert weak.status_code == 400 and "password" in weak.data["error"]["details"]["fields"]


def test_register_cannot_self_assign_privileged_roles(anon):
    r = register(anon, roles=["moderator"])
    assert r.status_code == 400


def test_unauthenticated_requests_get_401_with_error_envelope(anon):
    r = anon.get("/api/v1/auth/me/")
    assert r.status_code == 401
    err = r.data["error"]
    assert err["code"] == "not_authenticated" and err["request_id"].startswith("req_")
    assert r["X-Request-ID"] == err["request_id"]


def test_login_logout_and_bad_credentials(anon, artist):
    bad = anon.post("/api/v1/auth/login/", {"email": artist.email, "password": "nope"},
                    format="json")
    assert bad.status_code == 401 and bad.data["error"]["code"] == "invalid_credentials"
    ok = anon.post("/api/v1/auth/login/", {"email": "ARTIST@example.com", "password": PASSWORD},
                   format="json")
    assert ok.status_code == 200
    assert anon.get("/api/v1/auth/me/").status_code == 200
    assert anon.post("/api/v1/auth/logout/").status_code == 204
    assert anon.get("/api/v1/auth/me/").status_code == 401
    assert AuditEvent.objects.filter(action="auth.login_failed").exists()


def test_login_requires_csrf_token_for_browser_clients(artist):
    client = APIClient(enforce_csrf_checks=True)
    r = client.post("/api/v1/auth/login/", {"email": artist.email, "password": PASSWORD},
                    format="json")
    assert r.status_code == 403
    client.get("/api/v1/auth/csrf/")
    token = client.cookies["csrftoken"].value
    r = client.post("/api/v1/auth/login/", {"email": artist.email, "password": PASSWORD},
                    format="json", HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200


def test_login_is_rate_limited(anon, artist, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "auth", "3/min")
    for _ in range(3):
        anon.post("/api/v1/auth/login/", {"email": artist.email, "password": "x"}, format="json")
    r = anon.post("/api/v1/auth/login/", {"email": artist.email, "password": PASSWORD},
                  format="json")
    assert r.status_code == 429 and r.data["error"]["code"] == "rate_limited"
    assert "Retry-After" in r


def test_password_reset_is_generic_and_token_works_once(anon, artist):
    unknown = anon.post("/api/v1/auth/password/reset/", {"email": "ghost@example.com"},
                        format="json")
    known = anon.post("/api/v1/auth/password/reset/", {"email": artist.email}, format="json")
    assert unknown.status_code == known.status_code == 202
    assert unknown.data == known.data  # no account enumeration
    assert len(mail.outbox) == 1
    uid, token = re.search(r"uid=([^&]+)&token=(\S+)", mail.outbox[0].body).groups()
    new = "a-brand-new-long-passphrase"
    r = anon.post("/api/v1/auth/password/reset/confirm/",
                  {"uid": uid, "token": token, "new_password": new}, format="json")
    assert r.status_code == 204
    again = anon.post("/api/v1/auth/password/reset/confirm/",
                      {"uid": uid, "token": token, "new_password": new + "x"}, format="json")
    assert again.status_code == 400  # token is single-use (password hash changed)
    assert anon.post("/api/v1/auth/login/", {"email": artist.email, "password": new},
                     format="json").status_code == 200


def test_suspension_revokes_existing_sessions(anon, artist, admin_user):
    anon.post("/api/v1/auth/login/", {"email": artist.email, "password": PASSWORD}, format="json")
    assert anon.get("/api/v1/auth/me/").status_code == 200
    set_account_status(actor=admin_user, user=artist, status=AccountStatus.SUSPENDED)
    assert anon.get("/api/v1/auth/me/").status_code == 401
    r = anon.post("/api/v1/auth/login/", {"email": artist.email, "password": PASSWORD},
                  format="json")
    assert r.status_code == 401


def test_user_can_add_organizer_role_to_their_account(client_for, artist):
    c = client_for(artist)
    r = c.post("/api/v1/auth/me/roles/", {"role": "organizer"}, format="json")
    assert r.status_code == 201 and set(r.data["roles"]) == {"artist", "organizer"}
    assert c.post("/api/v1/auth/me/roles/", {"role": "administrator"},
                  format="json").status_code == 400


def test_health_endpoints(anon):
    assert anon.get("/api/v1/health/").data == {"status": "ok"}
    assert anon.get("/api/v1/health/ready/").data["database"] == "ok"

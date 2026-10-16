from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.identity.models import Role, RoleAssignment, User
from apps.outbox.services import process_pending
from apps.profiles.services import create_profile_for_user

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()  # throttle counters live in the cache
    yield
    cache.clear()


def make_user(email, *roles, name=None):
    user = User.objects.create_user(email=email, password=PASSWORD,
                                    display_name=name or email.split("@")[0])
    for role in roles:
        RoleAssignment.objects.create(user=user, role=role)
    create_profile_for_user(user)
    return user


@pytest.fixture
def artist(db):
    return make_user("artist@example.com", Role.ARTIST, name="Asha Artist")


@pytest.fixture
def artist2(db):
    return make_user("artist2@example.com", Role.ARTIST, name="Ben Bassist")


@pytest.fixture
def organizer(db):
    return make_user("organizer@example.com", Role.ORGANIZER, name="Olivia Organizer")


@pytest.fixture
def organizer2(db):
    return make_user("organizer2@example.com", Role.ORGANIZER, name="Omar Other")


@pytest.fixture
def member(db):
    return make_user("member@example.com", name="Mia Member")


@pytest.fixture
def moderator(db):
    return make_user("mod@example.com", Role.MODERATOR, name="Moe Moderator")


@pytest.fixture
def admin_user(db):
    return make_user("admin@example.com", Role.ADMINISTRATOR, name="Ada Admin")


@pytest.fixture
def client_for():
    def _client(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return _client


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def run_outbox():
    """Deliver outbox events (tests run with OUTBOX_DISPATCH=manual)."""
    return process_pending


def future(days=7):
    return (timezone.now() + timedelta(days=days)).isoformat()


@pytest.fixture
def published_event(client_for, organizer):
    c = client_for(organizer)
    r = c.post("/api/v1/events/", {
        "title": "Friday Open Mic", "starts_at": future(10), "location_text": "Bengaluru",
        "timezone": "Asia/Kolkata",
    }, format="json")
    assert r.status_code == 201, r.data
    r = c.post(f"/api/v1/events/{r.data['id']}/publish/")
    assert r.status_code == 200, r.data
    return r.data


def opportunity_payload(**overrides):
    payload = {
        "title": "Singer slot", "description": "10-minute acoustic set",
        "opportunity_type": "open_mic_slot", "compensation_type": "unpaid",
        "location_text": "Bengaluru", "application_deadline": future(5), "capacity": 1,
        "genres": ["acoustic"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def make_opportunity(client_for, organizer):
    def _make(owner=None, publish=True, **overrides):
        c = client_for(owner or organizer)
        r = c.post("/api/v1/opportunities/", opportunity_payload(**overrides), format="json")
        assert r.status_code == 201, r.data
        if publish:
            r = c.post(f"/api/v1/opportunities/{r.data['id']}/publish/")
            assert r.status_code == 200, r.data
        return r.data

    return _make


@pytest.fixture
def apply(client_for):
    def _apply(user, opportunity_id, **body):
        return client_for(user).post(
            f"/api/v1/opportunities/{opportunity_id}/applications/", body, format="json"
        )

    return _apply

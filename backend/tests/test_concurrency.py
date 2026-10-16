"""Race-condition tests. These use real transactions and separate DB connections per thread,
so they exercise PostgreSQL row locks and unique constraints rather than test-transaction
illusions."""

import threading

import pytest
from django.db import connection

from apps.identity.models import Role
from apps.messaging.models import Conversation
from apps.messaging.services import start_direct_conversation
from apps.opportunities import services as opp_services
from apps.opportunities.models import Application, Booking, Opportunity
from shared.errors import Conflict

from .conftest import make_user

pytestmark = pytest.mark.django_db(transaction=True)


def race(fn, args_list):
    barrier = threading.Barrier(len(args_list))
    results = []

    def worker(args):
        barrier.wait()
        try:
            results.append(("ok", fn(*args)))
        except Exception as exc:  # noqa: BLE001 - we assert on outcome types below
            results.append(("err", exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(a,)) for a in args_list]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_acceptances_never_exceed_capacity():
    organizer = make_user("org@example.com", Role.ORGANIZER)
    opp = Opportunity.objects.create(
        owner=organizer, title="One slot", description="d", opportunity_type="paid_gig",
        compensation_type="unpaid", location_text="x", capacity=2, status="published",
    )
    apps = []
    for i in range(6):
        artist = make_user(f"a{i}@example.com", Role.ARTIST)
        apps.append(Application.objects.create(opportunity=opp, applicant=artist))

    results = race(
        lambda app_id: opp_services.transition_application(organizer, app_id, "accepted"),
        [(a.id,) for a in apps],
    )

    ok = [r for r in results if r[0] == "ok"]
    errors = [r[1] for r in results if r[0] == "err"]
    assert len(ok) == 2
    assert all(isinstance(e, Conflict) and e.code == "capacity_full" for e in errors)
    assert Booking.objects.filter(opportunity=opp).count() == 2
    assert Application.objects.filter(opportunity=opp, status="accepted").count() == 2


def test_concurrent_duplicate_applications_create_one_row():
    organizer = make_user("org@example.com", Role.ORGANIZER)
    artist = make_user("artist@example.com", Role.ARTIST)
    opp = Opportunity.objects.create(
        owner=organizer, title="Slot", description="d", opportunity_type="paid_gig",
        compensation_type="unpaid", location_text="x", status="published",
    )
    results = race(lambda: opp_services.submit_application(artist, opp.id), [()] * 5)
    assert sum(1 for r in results if r[0] == "ok") == 1
    assert all(r[1].code == "already_applied" for r in results if r[0] == "err")
    assert Application.objects.filter(opportunity=opp).count() == 1


def test_concurrent_conversation_starts_converge_on_one_conversation():
    a = make_user("a@example.com")
    b = make_user("b@example.com")
    results = race(
        lambda x, y: start_direct_conversation(x, y.id)[0].id,
        [(a, b), (b, a), (a, b), (b, a)],
    )
    assert all(r[0] == "ok" for r in results), results
    assert len({r[1] for r in results}) == 1
    assert Conversation.objects.count() == 1

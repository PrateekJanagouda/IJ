"""Publish domain events and dispatch them to in-process subscribers."""

import logging
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import OutboxEvent

logger = logging.getLogger(__name__)
_subscribers = defaultdict(list)


def subscribe(event_type, handler):
    """Register a handler(payload) for an event type. Called from AppConfig.ready()."""
    if handler not in _subscribers[event_type]:
        _subscribers[event_type].append(handler)


def publish(event_type, payload):
    """Record an event. Must run inside the transaction that performs the state change."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("outbox.publish() must be called inside transaction.atomic().")
    event = OutboxEvent.objects.create(event_type=event_type, payload=payload)
    transaction.on_commit(_schedule_dispatch)
    return event


def _schedule_dispatch():
    mode = settings.OUTBOX_DISPATCH
    if mode == "inline":
        process_pending()
    elif mode == "celery":
        from .tasks import dispatch_outbox

        dispatch_outbox.delay()


def process_pending(batch_size=100):
    """Deliver pending events. Safe to run concurrently: rows are claimed with SKIP LOCKED.

    Each event is attempted at most once per call, so a failing handler is retried on the
    next sweep instead of spinning here.
    """
    attempted = set()
    while True:
        with transaction.atomic():
            events = list(
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(processed_at__isnull=True, attempts__lt=settings.OUTBOX_MAX_ATTEMPTS)
                .exclude(pk__in=attempted)
                .order_by("created_at")[:batch_size]
            )
            if not events:
                return len(attempted)
            for event in events:
                attempted.add(event.pk)
                _deliver(event)


def _deliver(event):
    try:
        # Savepoint: one failing handler must not roll back the whole batch.
        with transaction.atomic():
            for handler in _subscribers.get(event.event_type, []):
                handler(event.payload)
    except Exception as exc:
        logger.exception("Outbox handler failed for %s %s", event.event_type, event.id)
        OutboxEvent.objects.filter(pk=event.pk).update(
            attempts=F("attempts") + 1, last_error=repr(exc)[:2000]
        )
        return
    OutboxEvent.objects.filter(pk=event.pk).update(
        processed_at=timezone.now(), attempts=F("attempts") + 1
    )

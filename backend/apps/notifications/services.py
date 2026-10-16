from django.db import transaction
from django.utils import timezone

from apps.trust_safety import services as safety
from shared.errors import NotFound

from .models import Notification


def notify(*, recipient_id, notification_type, actor_id=None, resource_type="",
           resource_id=None, payload=None, dedup_key=None, refresh=False):
    """Create an in-app notification. Idempotent per (recipient, dedup_key), which makes
    outbox redelivery safe. With refresh=True a duplicate is bumped back to unread instead
    (used for "new messages in conversation X" so a chat produces one entry, not hundreds).
    """
    if actor_id and str(actor_id) == str(recipient_id):
        return None
    if actor_id and safety.is_blocked(actor_id, recipient_id):
        return None
    now = timezone.now()
    fields = {
        "actor_id": actor_id,
        "notification_type": notification_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "payload": payload or {},
    }
    if dedup_key is None:
        return Notification.objects.create(recipient_id=recipient_id, created_at=now, **fields)
    with transaction.atomic():
        notification, created = Notification.objects.select_for_update().get_or_create(
            recipient_id=recipient_id, deduplication_key=dedup_key,
            defaults={**fields, "created_at": now},
        )
        if not created and refresh:
            for key, value in fields.items():
                setattr(notification, key, value)
            notification.created_at = now
            notification.read_at = None
            notification.save()
    return notification


def for_user(user, *, unread_only=False):
    qs = Notification.objects.filter(recipient=user).select_related("actor")
    if unread_only:
        qs = qs.filter(read_at__isnull=True)
    return qs


def unread_count(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(user, notification_id):
    notification = Notification.objects.filter(id=notification_id, recipient=user).first()
    if notification is None:
        raise NotFound("Notification not found.")
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )


def mark_conversation_read(user, conversation_id):
    Notification.objects.filter(
        recipient=user, deduplication_key=f"message:{conversation_id}", read_at__isnull=True
    ).update(read_at=timezone.now())

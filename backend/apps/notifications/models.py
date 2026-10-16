import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    """Derived signal, never the source of truth (the application row is authoritative).
    Payloads stay small and never contain private message bodies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    notification_type = models.CharField(max_length=50)
    resource_type = models.CharField(max_length=30, blank=True)
    resource_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    # NULL (not "") means "no dedup": the partial unique constraint ignores NULLs.
    deduplication_key = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "notifications"
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "deduplication_key"],
                condition=Q(deduplication_key__isnull=False),
                name="uniq_notification_dedup",
            )
        ]
        indexes = [
            models.Index(fields=["recipient", "-created_at", "-id"]),
            models.Index(
                fields=["recipient", "-created_at"],
                condition=Q(read_at__isnull=True),
                name="notif_unread_idx",
            ),
        ]

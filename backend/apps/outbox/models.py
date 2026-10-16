import uuid

from django.db import models


class OutboxEvent(models.Model):
    """Transactional outbox: a domain event written in the same transaction as the state
    change it describes. A dispatcher delivers it to subscribers at-least-once, so every
    subscriber must be idempotent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "outbox_events"
        indexes = [
            models.Index(
                fields=["created_at"],
                name="outbox_pending_idx",
                condition=models.Q(processed_at__isnull=True),
            )
        ]

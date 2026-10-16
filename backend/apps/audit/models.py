import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """Append-only record of security-sensitive and consequential actions.

    Never store passwords, session tokens or private message bodies in `metadata`.
    """

    class ActorType(models.TextChoices):
        USER = "user"
        SYSTEM = "system"
        AGENT = "agent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    actor_type = models.CharField(max_length=10, choices=ActorType.choices, default="user")
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=40, blank=True)
    resource_id = models.UUIDField(null=True, blank=True)
    outcome = models.CharField(max_length=20, default="success")
    request_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_events"
        indexes = [
            models.Index(fields=["resource_type", "resource_id", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

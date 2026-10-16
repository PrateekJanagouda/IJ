from django.conf import settings
from django.db import models
from django.db.models import F, Q

from shared.models import TimeStampedModel, UUIDModel


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_made"
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_blocks"
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="uniq_block"),
            models.CheckConstraint(condition=~Q(blocker=F("blocked")), name="no_self_block"),
        ]
        indexes = [models.Index(fields=["blocked", "blocker"])]


class TargetType(models.TextChoices):
    USER = "user"
    POST = "post"
    COMMENT = "comment"
    MESSAGE = "message"
    OPPORTUNITY = "opportunity"
    EVENT = "event"


class Report(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open"
        IN_REVIEW = "in_review"
        RESOLVED = "resolved"
        DISMISSED = "dismissed"

    class Reason(models.TextChoices):
        SPAM = "spam"
        HARASSMENT = "harassment"
        SCAM = "scam"
        IMPERSONATION = "impersonation"
        MISLEADING_LISTING = "misleading_listing"
        INAPPROPRIATE = "inappropriate"
        OTHER = "other"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_made"
    )
    # Polymorphic target: existence and reporter access are validated in services.
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.UUIDField()
    reason_code = models.CharField(max_length=30, choices=Reason.choices)
    description = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="+",
    )
    resolution_note = models.TextField(max_length=2000, blank=True)

    class Meta:
        db_table = "reports"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["reporter", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]


class ModerationAction(UUIDModel):
    """Append-only history of moderation decisions."""

    class ActionType(models.TextChoices):
        HIDE_CONTENT = "hide_content"
        RESTORE_CONTENT = "restore_content"
        CLOSE_LISTING = "close_listing"
        SUSPEND_USER = "suspend_user"
        REINSTATE_USER = "reinstate_user"
        DISMISS = "dismiss"

    report = models.ForeignKey(
        Report, null=True, blank=True, on_delete=models.PROTECT, related_name="actions"
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.UUIDField()
    reason_code = models.CharField(max_length=30)
    note = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "moderation_actions"
        ordering = ["created_at"]

from django.conf import settings
from django.db import models

from shared.models import TimeStampedModel, UUIDModel


class Conversation(TimeStampedModel):
    class Type(models.TextChoices):
        DIRECT = "direct"  # group chats are out of MVP scope

    conversation_type = models.CharField(max_length=10, choices=Type.choices, default="direct")
    # Canonical "<smaller uuid>:<larger uuid>" for direct chats. The unique constraint makes
    # concurrent "start conversation" requests converge on one row.
    pair_key = models.CharField(  # noqa: DJ001 - NULL for future group chats (unique ignores NULL)
        max_length=80, null=True, blank=True, unique=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "conversations"


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_memberships"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "conversation_participants"
        constraints = [
            models.UniqueConstraint(fields=["conversation", "user"], name="uniq_participant"),
        ]
        indexes = [models.Index(fields=["user", "archived_at", "conversation"])]


class Message(UUIDModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "messages"
        indexes = [models.Index(fields=["conversation", "-created_at", "-id"])]

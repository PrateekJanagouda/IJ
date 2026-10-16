"""Direct messaging. Membership is checked on every read and write; possessing a
conversation ID grants nothing. Messages are durable in PostgreSQL; any real-time
transport added later only delivers what is already persisted."""

from datetime import UTC, datetime

from django.db import IntegrityError, transaction
from django.db.models import Count, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.identity import services as identity
from apps.outbox import services as outbox
from apps.trust_safety import services as safety
from shared.errors import Conflict, Forbidden, NotFound, ValidationFailed

from .models import Conversation, ConversationParticipant, Message


def _pair_key(a_id, b_id):
    first, second = sorted([str(a_id), str(b_id)])
    return f"{first}:{second}"


@transaction.atomic
def start_direct_conversation(actor, recipient_id):
    recipient = identity.get_active_user(recipient_id)
    if recipient.id == actor.id:
        raise ValidationFailed("You cannot message yourself.", code="self_message")
    if safety.is_blocked(actor.id, recipient.id):
        raise Forbidden("You cannot message this user.", code="blocked")
    key = _pair_key(actor.id, recipient.id)
    existing = Conversation.objects.filter(pair_key=key).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(pair_key=key, created_by=actor)
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conversation, user=actor),
                ConversationParticipant(conversation=conversation, user=recipient),
            ])
    except IntegrityError:
        # A concurrent request created it first; both callers get the same conversation.
        return Conversation.objects.get(pair_key=key), False
    return conversation, True


def _membership(actor, conversation_id):
    membership = (
        ConversationParticipant.objects.select_related("conversation")
        .filter(conversation_id=conversation_id, user=actor)
        .first()
    )
    if membership is None:
        raise NotFound("Conversation not found.")
    return membership


def _other_participant_ids(conversation_id, actor_id):
    return list(
        ConversationParticipant.objects.filter(conversation_id=conversation_id)
        .exclude(user_id=actor_id)
        .values_list("user_id", flat=True)
    )


def conversations_for(actor, *, archived=False):
    """Inbox for `actor`, newest activity first, with unread count and last-message preview."""
    epoch = Value(datetime(1970, 1, 1, tzinfo=UTC))
    my_last_read = ConversationParticipant.objects.filter(
        conversation=OuterRef("pk"), user=actor
    ).values("last_read_at")[:1]
    unread = (
        Message.objects.filter(
            conversation=OuterRef("pk"),
            deleted_at__isnull=True,
            created_at__gt=Coalesce(OuterRef("my_last_read_at"), epoch),
        )
        .exclude(sender=actor)
        .order_by()
        .values("conversation")
        .annotate(n=Count("id"))
        .values("n")[:1]
    )
    last_message = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at")
    return (
        Conversation.objects.filter(
            participants__user=actor, participants__archived_at__isnull=not archived
        )
        .annotate(my_last_read_at=Subquery(my_last_read))
        .annotate(
            unread_count=Coalesce(Subquery(unread), 0),
            last_message_body=Subquery(last_message.values("body")[:1]),
            last_message_deleted_at=Subquery(last_message.values("deleted_at")[:1]),
            last_message_sender_id=Subquery(last_message.values("sender_id")[:1]),
            sort_at=Coalesce("last_message_at", "created_at"),
        )
        .prefetch_related("participants__user__profile")
        .order_by(F("sort_at").desc(), "-id")
    )


def get_conversation(actor, conversation_id):
    membership = _membership(actor, conversation_id)
    archived = membership.archived_at is not None
    return conversations_for(actor, archived=archived).get(id=conversation_id)


def messages_for(actor, conversation_id):
    _membership(actor, conversation_id)
    return Message.objects.filter(conversation_id=conversation_id).select_related("sender")


@transaction.atomic
def send_message(actor, conversation_id, *, body):
    membership = _membership(actor, conversation_id)
    body = (body or "").strip()
    if not body:
        raise ValidationFailed(details={"fields": {"body": ["Message cannot be empty."]}})
    others = _other_participant_ids(conversation_id, actor.id)
    for other_id in others:
        if safety.is_blocked(actor.id, other_id):
            raise Forbidden("You cannot message this user.", code="blocked")
    from apps.identity.models import User

    if User.objects.filter(id__in=others, is_active=False).exists():
        raise Conflict("This account is unavailable.", code="recipient_unavailable")

    conversation = Conversation.objects.select_for_update().get(id=conversation_id)
    message = Message.objects.create(conversation=conversation, sender=actor, body=body)
    conversation.last_message_at = message.created_at
    conversation.save(update_fields=["last_message_at", "updated_at"])
    # Sender has read everything up to their own message; recipients see it un-archived.
    membership.last_read_at = message.created_at
    membership.save(update_fields=["last_read_at"])
    ConversationParticipant.objects.filter(conversation=conversation, user_id__in=others).update(
        archived_at=None
    )
    outbox.publish(
        "message.created",
        {
            "message_id": str(message.id),
            "conversation_id": str(conversation.id),
            "sender_id": str(actor.id),
            "recipient_ids": [str(o) for o in others],
        },
    )
    return message


def mark_read(actor, conversation_id):
    membership = _membership(actor, conversation_id)
    membership.last_read_at = timezone.now()
    membership.save(update_fields=["last_read_at"])
    return membership


def set_archived(actor, conversation_id, archived):
    membership = _membership(actor, conversation_id)
    membership.archived_at = timezone.now() if archived else None
    membership.save(update_fields=["archived_at"])
    return membership


@transaction.atomic
def delete_message(actor, message_id):
    """Sender soft-deletes a message for everyone; the row is retained for moderation."""
    message = Message.objects.select_for_update().filter(id=message_id).first()
    if message is None:
        raise NotFound("Message not found.")
    _membership(actor, message.conversation_id)
    if message.sender_id != actor.id:
        raise Forbidden("You can only delete your own messages.")
    if message.deleted_at is None:
        message.deleted_at = timezone.now()
        message.save(update_fields=["deleted_at"])
    return message


def get_message_for_participant(actor, message_id):
    message = Message.objects.filter(id=message_id).first()
    if message is None:
        raise NotFound("Message not found.")
    _membership(actor, message.conversation_id)
    return message


def total_unread(actor):
    return sum(c.unread_count for c in conversations_for(actor))

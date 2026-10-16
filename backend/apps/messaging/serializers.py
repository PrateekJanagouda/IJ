from rest_framework import serializers

from shared.serializers import UserSummarySerializer

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSummarySerializer(read_only=True)
    body = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "conversation_id", "sender", "body", "is_deleted", "created_at"]

    def get_body(self, message) -> str | None:
        return None if message.deleted_at else message.body

    def get_is_deleted(self, message) -> bool:
        return message.deleted_at is not None


class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True, default=0)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "conversation_type", "participants", "unread_count", "last_message",
                  "last_message_at", "created_at"]

    def get_participants(self, conversation) -> list[dict]:
        return [UserSummarySerializer(p.user).data for p in conversation.participants.all()]

    def get_last_message(self, conversation) -> dict | None:
        if not getattr(conversation, "last_message_sender_id", None):
            return None
        deleted = conversation.last_message_deleted_at is not None
        return {
            "sender_id": str(conversation.last_message_sender_id),
            "preview": None if deleted else (conversation.last_message_body or "")[:140],
            "is_deleted": deleted,
        }


class StartConversationSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)


class ArchiveSerializer(serializers.Serializer):
    archived = serializers.BooleanField()

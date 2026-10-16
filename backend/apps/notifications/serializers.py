from rest_framework import serializers

from shared.serializers import UserSummarySerializer

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True, allow_null=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "notification_type", "actor", "resource_type", "resource_id", "payload",
                  "is_read", "read_at", "created_at"]

    def get_is_read(self, notification) -> bool:
        return notification.read_at is not None

from rest_framework import serializers


class UserSummarySerializer(serializers.Serializer):
    """Minimal public identity used wherever another user is referenced."""

    id = serializers.UUIDField()
    display_name = serializers.CharField()
    profile_id = serializers.SerializerMethodField()

    def get_profile_id(self, user) -> str | None:
        profile = getattr(user, "profile", None)
        return str(profile.id) if profile else None


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class ConfirmReasonSerializer(ReasonSerializer):
    confirm = serializers.BooleanField(required=False, default=False)


class UnreadCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()


class StatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField(required=False)

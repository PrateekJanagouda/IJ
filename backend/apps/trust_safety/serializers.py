from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from shared.serializers import UserSummarySerializer

from .models import ModerationAction, Report, TargetType


class ReportInputSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=TargetType.choices)
    target_id = serializers.UUIDField()
    reason_code = serializers.ChoiceField(choices=Report.Reason.choices)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class MyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "target_type", "target_id", "reason_code", "status", "created_at"]


class ModerationActionSerializer(serializers.ModelSerializer):
    moderator = UserSummarySerializer(read_only=True)

    class Meta:
        model = ModerationAction
        fields = ["id", "action_type", "reason_code", "note", "moderator", "created_at"]


class ModeratorReportSerializer(serializers.ModelSerializer):
    reporter = UserSummarySerializer(read_only=True)
    actions = ModerationActionSerializer(many=True, read_only=True)

    class Meta:
        model = Report
        fields = ["id", "reporter", "target_type", "target_id", "reason_code", "description",
                  "status", "resolution_note", "actions", "created_at", "updated_at"]


class ModerationActionInputSerializer(serializers.Serializer):
    action_type = serializers.ChoiceField(choices=ModerationAction.ActionType.choices)
    reason_code = serializers.CharField(max_length=30)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class BlockSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    @extend_schema_field(UserSummarySerializer)
    def get_user(self, block):
        return UserSummarySerializer(block.blocked).data


class BlockInputSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()

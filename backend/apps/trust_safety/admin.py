from django.contrib import admin

from .models import ModerationAction, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["created_at", "target_type", "reason_code", "status"]
    list_filter = ["status", "target_type", "reason_code"]

    def has_change_permission(self, request, obj=None):
        return False  # act through the moderation API so actions are recorded


@admin.register(ModerationAction)
class ModerationActionAdmin(ReportAdmin):
    list_display = ["created_at", "action_type", "target_type", "moderator"]
    list_filter = ["action_type"]

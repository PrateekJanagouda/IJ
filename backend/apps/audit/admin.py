from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only: the audit trail is append-only."""

    list_display = ["created_at", "action", "actor", "resource_type", "resource_id", "outcome"]
    list_filter = ["action", "outcome", "actor_type"]
    search_fields = ["request_id", "resource_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

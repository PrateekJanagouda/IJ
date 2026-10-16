from django.contrib import admin

from .models import RoleAssignment, User


class RoleInline(admin.TabularInline):
    model = RoleAssignment
    extra = 0


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "display_name", "account_status", "is_staff", "created_at"]
    list_filter = ["account_status", "is_staff"]
    search_fields = ["email", "display_name"]
    exclude = ["password", "user_permissions", "groups"]
    readonly_fields = ["last_login", "created_at", "updated_at"]
    inlines = [RoleInline]

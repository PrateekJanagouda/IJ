from django.contrib import admin

from .models import Application, Booking, Event, Opportunity


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "status", "starts_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["title"]


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "event", "status", "capacity", "application_deadline"]
    list_filter = ["status", "opportunity_type"]
    search_fields = ["title"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """Status changes must go through domain services (history + notifications)."""

    list_display = ["opportunity", "applicant", "status", "submitted_at"]
    list_filter = ["status"]

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(ApplicationAdmin):
    list_display = ["opportunity", "performer", "status", "selected_at"]

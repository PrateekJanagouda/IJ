import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from rest_framework import serializers

from apps.profiles.models import Venue
from apps.profiles.serializers import PortfolioItemSerializer
from shared.serializers import UserSummarySerializer

from . import services
from .models import Application, ApplicationStatusChange, Booking, Event, Opportunity


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise serializers.ValidationError("Use an IANA time zone such as Asia/Kolkata.") from exc
    return value


class VenueRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    city = serializers.CharField()


class EventSerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    venue = VenueRefSerializer(read_only=True, allow_null=True)
    viewer_can_manage = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "owner", "venue", "title", "description", "starts_at", "ends_at", "timezone",
            "location_text", "is_online", "external_ticket_url", "visibility", "status",
            "published_at", "cancelled_at", "cancellation_reason", "viewer_can_manage",
            "share_url", "created_at", "updated_at",
        ]

    def get_viewer_can_manage(self, event) -> bool:
        request = self.context.get("request")
        return services.can_manage_event(request and request.user, event)

    def get_share_url(self, event) -> str:
        return f"{settings.FRONTEND_BASE_URL}/events/{event.id}"


class EventInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=140)
    description = serializers.CharField(max_length=8000, required=False, allow_blank=True)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    timezone = serializers.CharField(max_length=64, required=False, validators=[validate_timezone])
    location_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_online = serializers.BooleanField(required=False)
    external_ticket_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=Event.Visibility.choices, required=False)
    venue_id = serializers.PrimaryKeyRelatedField(
        queryset=Venue.objects.all(), source="venue", required=False, allow_null=True
    )


class OpportunitySerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    event = serializers.SerializerMethodField()
    genres = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)
    skills = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)
    accepting_applications = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = [
            "id", "event", "owner", "title", "description", "opportunity_type",
            "compensation_type", "compensation_amount", "currency", "capacity",
            "application_deadline", "starts_at", "ends_at", "timezone", "location_text",
            "is_online", "requirements", "genres", "skills", "status",
            "accepting_applications", "published_at", "cancelled_at", "cancellation_reason",
            "share_url", "created_at", "updated_at",
        ]

    def get_event(self, opp) -> dict | None:
        if not opp.event_id:
            return None
        e = opp.event
        return {"id": str(e.id), "title": e.title, "status": e.status, "starts_at": e.starts_at}

    def get_accepting_applications(self, opp) -> bool:
        return services.accepting_applications(opp)

    def get_share_url(self, opp) -> str:
        return f"{settings.FRONTEND_BASE_URL}/opportunities/{opp.id}"


class OpportunityDetailSerializer(OpportunitySerializer):
    """Adds viewer-specific fields. Manager-only counts are never shown to the public."""

    viewer_can_manage = serializers.SerializerMethodField()
    viewer_application = serializers.SerializerMethodField()
    manager_stats = serializers.SerializerMethodField()

    class Meta(OpportunitySerializer.Meta):
        fields = OpportunitySerializer.Meta.fields + [
            "viewer_can_manage", "viewer_application", "manager_stats",
        ]

    def _user(self):
        request = self.context.get("request")
        return request.user if request else None

    def get_viewer_can_manage(self, opp) -> bool:
        return services.can_manage_opportunity(self._user(), opp)

    def get_viewer_application(self, opp) -> dict | None:
        user = self._user()
        if not user or not user.is_authenticated:
            return None
        app = opp.applications.filter(applicant=user).only("id", "status").first()
        return {"id": str(app.id), "status": app.status} if app else None

    def get_manager_stats(self, opp) -> dict | None:
        if not services.can_manage_opportunity(self._user(), opp):
            return None
        counts = {s: 0 for s in Application.Status.values}
        for row in opp.applications.values("status").order_by():
            counts[row["status"]] += 1
        return {"applications": counts, "confirmed_bookings": services.active_booking_count(opp)}


class OpportunityInputSerializer(serializers.Serializer):
    event_id = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.all(), source="event", required=False, allow_null=True
    )
    title = serializers.CharField(max_length=140)
    description = serializers.CharField(max_length=8000)
    opportunity_type = serializers.ChoiceField(choices=Opportunity.Type.choices)
    compensation_type = serializers.ChoiceField(choices=Opportunity.Compensation.choices)
    compensation_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    capacity = serializers.IntegerField(min_value=1, max_value=500, required=False)
    application_deadline = serializers.DateTimeField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    timezone = serializers.CharField(max_length=64, required=False, validators=[validate_timezone])
    location_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_online = serializers.BooleanField(required=False)
    requirements = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    genres = serializers.ListField(child=serializers.SlugField(), required=False, max_length=10)
    skills = serializers.ListField(child=serializers.SlugField(), required=False, max_length=15)

    def validate_currency(self, value):
        value = value.upper()
        if value and not re.fullmatch(r"[A-Z]{3}", value):
            raise serializers.ValidationError("Use an ISO 4217 code such as INR or USD.")
        return value


class DiscoveryQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=100, required=False)
    type = serializers.ChoiceField(choices=Opportunity.Type.choices, required=False)
    compensation = serializers.ChoiceField(choices=Opportunity.Compensation.choices,
                                           required=False)
    genre = serializers.SlugField(required=False)
    skill = serializers.SlugField(required=False)
    location = serializers.CharField(max_length=100, required=False)
    starts_after = serializers.DateTimeField(required=False)
    starts_before = serializers.DateTimeField(required=False)
    event = serializers.UUIDField(required=False)
    include_closed = serializers.BooleanField(required=False, default=False)


class EventQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=100, required=False)
    location = serializers.CharField(max_length=100, required=False)
    starts_after = serializers.DateTimeField(required=False)
    starts_before = serializers.DateTimeField(required=False)


class OpportunityRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    status = serializers.CharField()
    event_id = serializers.UUIDField(allow_null=True)
    starts_at = serializers.DateTimeField(allow_null=True)


class BookingRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()


class ApplicationSerializer(serializers.ModelSerializer):
    opportunity = OpportunityRefSerializer(read_only=True)
    applicant = UserSummarySerializer(read_only=True)
    portfolio_items = PortfolioItemSerializer(many=True, read_only=True)
    booking = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id", "opportunity", "applicant", "status", "cover_note", "portfolio_items",
            "booking", "submitted_at", "decided_at", "updated_at",
        ]

    def get_booking(self, application) -> dict | None:
        booking = getattr(application, "booking", None)
        return BookingRefSerializer(booking).data if booking else None


class ApplicationInputSerializer(serializers.Serializer):
    cover_note = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    portfolio_item_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=10
    )


class StatusChangeSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)

    class Meta:
        model = ApplicationStatusChange
        fields = ["id", "from_status", "to_status", "actor", "reason", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    opportunity = OpportunityRefSerializer(read_only=True)
    performer = UserSummarySerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "opportunity", "application_id", "performer", "status", "selected_at",
            "cancelled_at", "cancellation_reason", "completed_at",
        ]

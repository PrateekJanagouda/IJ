from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.identity import services as identity
from apps.media import services as media
from shared.serializers import UserSummarySerializer

from .models import (
    ArtistDetails,
    Genre,
    OrganizerDetails,
    PortfolioItem,
    Profile,
    Skill,
    Venue,
    VenueBooking,
)


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["slug", "name"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["slug", "name"]


class PortfolioItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioItem
        fields = ["id", "title", "description", "item_type", "url", "position", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_url(self, value):
        if not value.lower().startswith(("https://", "http://")):
            raise serializers.ValidationError("Only http(s) links are allowed.")
        return value


class ArtistDetailsSerializer(serializers.ModelSerializer):
    genres = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)
    skills = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)

    class Meta:
        model = ArtistDetails
        fields = ["artist_name", "experience_summary", "genres", "skills"]
        read_only_fields = fields


class OrganizerDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizerDetails
        fields = ["organization_name", "verification_status"]
        read_only_fields = fields


class ProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(read_only=True)
    roles = serializers.SerializerMethodField()
    artist = serializers.SerializerMethodField()
    organizer = serializers.SerializerMethodField()
    portfolio = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    viewer_is_following = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id", "user_id", "display_name", "headline", "bio", "location_label", "visibility",
            "roles", "artist", "organizer", "portfolio", "follower_count", "following_count",
            "viewer_is_following", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_roles(self, profile) -> list[str]:
        public = {"artist", "organizer"}
        return sorted(identity.roles_of(profile.user) & public)

    @extend_schema_field(ArtistDetailsSerializer(allow_null=True))
    def get_artist(self, profile):
        details = getattr(profile, "artist", None)  # reverse 1:1 missing -> None
        return ArtistDetailsSerializer(details).data if details else None

    @extend_schema_field(OrganizerDetailsSerializer(allow_null=True))
    def get_organizer(self, profile):
        details = getattr(profile, "organizer", None)
        return OrganizerDetailsSerializer(details).data if details else None

    @extend_schema_field(PortfolioItemSerializer(many=True, allow_null=True))
    def get_portfolio(self, profile):
        if not self.context.get("include_portfolio", True):
            return None
        return PortfolioItemSerializer(profile.portfolio.all(), many=True).data

    def _counts(self, profile):
        from apps.social import services as social

        cache = self.context.setdefault("_follow_counts", {})
        if profile.user_id not in cache:
            cache[profile.user_id] = social.follow_counts(profile.user_id)
        return cache[profile.user_id]

    def get_follower_count(self, profile) -> int:
        return self._counts(profile)["followers"]

    def get_following_count(self, profile) -> int:
        return self._counts(profile)["following"]

    def get_viewer_is_following(self, profile) -> bool:
        from apps.social import services as social

        request = self.context.get("request")
        return social.is_following(request and request.user, profile.user_id)


class ProfileListSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(read_only=True)
    artist = ArtistDetailsSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = ["id", "user_id", "display_name", "headline", "location_label", "artist"]
        read_only_fields = fields


class ArtistInputSerializer(serializers.Serializer):
    artist_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    experience_summary = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    genres = serializers.ListField(child=serializers.SlugField(), required=False, max_length=10)
    skills = serializers.ListField(child=serializers.SlugField(), required=False, max_length=15)


class OrganizerInputSerializer(serializers.Serializer):
    organization_name = serializers.CharField(max_length=120, required=False, allow_blank=True)


class ProfileUpdateSerializer(serializers.Serializer):
    """Explicit allowlist of editable fields (no mass assignment)."""

    display_name = serializers.CharField(max_length=80, required=False)
    headline = serializers.CharField(max_length=140, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    location_label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=Profile._meta.get_field("visibility").choices,
                                         required=False)
    artist = ArtistInputSerializer(required=False)
    organizer = OrganizerInputSerializer(required=False)


class VenuePhotoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    url = serializers.CharField()


class VenueSerializer(serializers.ModelSerializer):
    viewer_is_manager = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    managers = serializers.SerializerMethodField()
    photo_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True,
                                      required=False, max_length=8)

    class Meta:
        model = Venue
        fields = ["id", "name", "headline", "description", "city", "address_text", "capacity",
                  "starting_price", "currency", "payment_terms", "amenities", "is_listed",
                  "photos", "photo_ids", "managers", "viewer_is_manager", "created_at",
                  "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at", "viewer_is_manager", "photos",
                            "managers"]

    def get_viewer_is_manager(self, venue) -> bool:
        from .services import is_venue_manager

        request = self.context.get("request")
        return is_venue_manager(request and request.user, venue.id)

    @extend_schema_field(VenuePhotoSerializer(many=True))
    def get_photos(self, venue):
        return [{"id": str(p.id), "kind": p.kind, "url": media.url_for(p.id)}
                for p in venue.photos.all()]

    @extend_schema_field(UserSummarySerializer(many=True))
    def get_managers(self, venue):
        return UserSummarySerializer([m.user for m in venue.memberships.all()], many=True).data


class BookedVenueSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    city = serializers.CharField()


class VenueBookingSerializer(serializers.ModelSerializer):
    venue = BookedVenueSerializer(read_only=True)
    requester = UserSummarySerializer(read_only=True)

    class Meta:
        model = VenueBooking
        fields = ["id", "venue", "requester", "date", "starts_at", "ends_at", "status", "message",
                  "expected_headcount", "decided_at", "created_at"]
        read_only_fields = fields


class VenueBookingInputSerializer(serializers.Serializer):
    """Send times with an offset, e.g. 2026-10-24T20:00:00+05:30. Slots may cross midnight."""

    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    message = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    expected_headcount = serializers.IntegerField(min_value=1, max_value=100000, required=False,
                                                  allow_null=True, default=None)


class VenueBlockInputSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    message = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class AvailabilitySlotSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.ChoiceField(
        choices=["booked", "blocked", "requested_by_you", "has_requests"])


class AvailabilitySerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    slots = AvailabilitySlotSerializer(many=True)


class VenueManagerSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()

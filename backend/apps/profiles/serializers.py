from rest_framework import serializers

from apps.identity import services as identity

from .models import ArtistDetails, Genre, OrganizerDetails, PortfolioItem, Profile, Skill, Venue


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


class OrganizerDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizerDetails
        fields = ["organization_name", "verification_status"]


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

    def get_roles(self, profile) -> list[str]:
        public = {"artist", "organizer"}
        return sorted(identity.roles_of(profile.user) & public)

    def get_artist(self, profile) -> dict | None:
        details = getattr(profile, "artist", None)  # reverse 1:1 missing -> None
        return ArtistDetailsSerializer(details).data if details else None

    def get_organizer(self, profile) -> dict | None:
        details = getattr(profile, "organizer", None)
        return OrganizerDetailsSerializer(details).data if details else None

    def get_portfolio(self, profile) -> list[dict] | None:
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


class VenueSerializer(serializers.ModelSerializer):
    viewer_is_manager = serializers.SerializerMethodField()

    class Meta:
        model = Venue
        fields = ["id", "name", "description", "city", "address_text", "capacity",
                  "viewer_is_manager", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at", "viewer_is_manager"]

    def get_viewer_is_manager(self, venue) -> bool:
        from .services import is_venue_manager

        request = self.context.get("request")
        return is_venue_manager(request and request.user, venue.id)


class VenueManagerSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()

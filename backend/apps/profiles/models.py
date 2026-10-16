from django.conf import settings
from django.db import models

from shared.models import TimeStampedModel


class Genre(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=80)

    class Meta:
        db_table = "genres"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Skill(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=80)

    class Meta:
        db_table = "skills"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Visibility(models.TextChoices):
    PUBLIC = "public"  # anyone, including visitors
    MEMBERS = "members"  # signed-in users
    PRIVATE = "private"  # owner only


class Profile(TimeStampedModel):
    """One core profile per account. Role-specific details hang off it, so one account can
    be both an artist and an organizer."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="profile"
    )
    display_name = models.CharField(max_length=80)
    headline = models.CharField(max_length=140, blank=True)
    bio = models.TextField(max_length=4000, blank=True)
    location_label = models.CharField(max_length=120, blank=True)  # city-level, not precise
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )

    class Meta:
        db_table = "profiles"
        indexes = [models.Index(fields=["visibility", "created_at"])]

    def __str__(self):
        return self.display_name


class ArtistDetails(models.Model):
    profile = models.OneToOneField(
        Profile, primary_key=True, on_delete=models.CASCADE, related_name="artist"
    )
    artist_name = models.CharField(max_length=120, blank=True)
    experience_summary = models.TextField(max_length=4000, blank=True)
    genres = models.ManyToManyField(Genre, blank=True, related_name="artists")
    skills = models.ManyToManyField(Skill, blank=True, related_name="artists")

    class Meta:
        db_table = "artist_profile_details"


class OrganizerDetails(models.Model):
    class Verification(models.TextChoices):
        UNVERIFIED = "unverified"
        VERIFIED = "verified"

    profile = models.OneToOneField(
        Profile, primary_key=True, on_delete=models.CASCADE, related_name="organizer"
    )
    organization_name = models.CharField(max_length=120, blank=True)
    verification_status = models.CharField(
        max_length=12, choices=Verification.choices, default=Verification.UNVERIFIED
    )

    class Meta:
        db_table = "organizer_profile_details"


class PortfolioItem(TimeStampedModel):
    """MVP portfolio entries are external links (rich media upload is P1)."""

    class ItemType(models.TextChoices):
        LINK = "link"
        IMAGE = "image"
        AUDIO = "audio"
        VIDEO = "video"

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="portfolio")
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=2000, blank=True)
    item_type = models.CharField(max_length=10, choices=ItemType.choices, default="link")
    url = models.URLField(max_length=500)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "portfolio_items"
        indexes = [models.Index(fields=["profile", "position", "created_at"])]
        ordering = ["position", "created_at"]


class Venue(TimeStampedModel):
    """A venue is its own entity managed by explicitly assigned accounts, not a person."""

    name = models.CharField(max_length=120)
    description = models.TextField(max_length=4000, blank=True)
    city = models.CharField(max_length=120, blank=True)
    address_text = models.CharField(max_length=255, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        db_table = "venues"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity__isnull=True) | models.Q(capacity__gt=0),
                name="venue_capacity_positive",
            )
        ]


class VenueMembership(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="venue_memberships"
    )
    role = models.CharField(max_length=20, default="manager")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "venue_memberships"
        constraints = [
            models.UniqueConstraint(fields=["venue", "user"], name="uniq_venue_member"),
        ]

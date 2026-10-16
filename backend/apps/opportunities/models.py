from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.profiles.models import Genre, PortfolioItem, Skill, Venue
from shared.models import TimeStampedModel, UUIDModel


class Event(TimeStampedModel):
    """The overall happening. Has zero or many opportunities (apply-able slots)."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"
        CANCELLED = "cancelled"
        COMPLETED = "completed"

    class Visibility(models.TextChoices):
        PUBLIC = "public"  # listed in discovery
        UNLISTED = "unlisted"  # reachable by link, not listed

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="events"
    )
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.PROTECT, related_name="events"
    )
    title = models.CharField(max_length=140)
    description = models.TextField(max_length=8000, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")  # IANA zone for display
    location_text = models.CharField(max_length=255, blank=True)
    is_online = models.BooleanField(default=False)
    external_ticket_url = models.URLField(max_length=500, blank=True)
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="+",
    )
    cancellation_reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        db_table = "events"
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(starts_at__isnull=True)
                | Q(ends_at__gte=F("starts_at")),
                name="event_ends_after_start",
            )
        ]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["status", "starts_at"]),
        ]

    def __str__(self):
        return self.title


class Opportunity(TimeStampedModel):
    """An individually apply-able slot, role or gig. `event` is optional (standalone gigs)."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"  # accepting applications until the deadline
        CLOSED = "closed"  # no new applications; selection may continue
        CANCELLED = "cancelled"
        COMPLETED = "completed"

    class Type(models.TextChoices):
        OPEN_MIC_SLOT = "open_mic_slot"
        PAID_GIG = "paid_gig"
        AUDITION = "audition"
        BAND_SLOT = "band_slot"
        DJ_SLOT = "dj_slot"
        HOST_ROLE = "host_role"
        OTHER = "other"

    class Compensation(models.TextChoices):
        UNPAID = "unpaid"
        PAID = "paid"
        REVENUE_SHARE = "revenue_share"
        NEGOTIABLE = "negotiable"

    event = models.ForeignKey(
        Event, null=True, blank=True, on_delete=models.PROTECT, related_name="opportunities"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opportunities"
    )
    title = models.CharField(max_length=140)
    description = models.TextField(max_length=8000)
    opportunity_type = models.CharField(max_length=20, choices=Type.choices)
    compensation_type = models.CharField(max_length=20, choices=Compensation.choices)
    compensation_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, blank=True)
    # Capacity unit: one accepted application (a solo artist or a group act) = one seat.
    capacity = models.PositiveIntegerField(default=1)
    application_deadline = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    location_text = models.CharField(max_length=255, blank=True)
    is_online = models.BooleanField(default=False)
    requirements = models.TextField(max_length=4000, blank=True)
    genres = models.ManyToManyField(Genre, blank=True, related_name="opportunities")
    skills = models.ManyToManyField(Skill, blank=True, related_name="opportunities")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        db_table = "opportunities"
        verbose_name_plural = "opportunities"
        constraints = [
            models.CheckConstraint(condition=Q(capacity__gt=0), name="opp_capacity_positive"),
            models.CheckConstraint(
                condition=Q(compensation_amount__isnull=True) | Q(compensation_amount__gte=0),
                name="opp_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(compensation_amount__isnull=True) | ~Q(currency=""),
                name="opp_currency_with_amount",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(starts_at__isnull=True)
                | Q(ends_at__gte=F("starts_at")),
                name="opp_ends_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["event", "status"]),
            models.Index(fields=["status", "application_deadline"]),
            models.Index(fields=["status", "starts_at"]),
        ]

    def __str__(self):
        return self.title


class Application(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "submitted"
        SHORTLISTED = "shortlisted"
        ACCEPTED = "accepted"
        DECLINED = "declined"
        WITHDRAWN = "withdrawn"

    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.PROTECT, related_name="applications"
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="applications"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    cover_note = models.TextField(max_length=4000, blank=True)
    portfolio_items = models.ManyToManyField(PortfolioItem, blank=True, related_name="+")
    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "applications"
        constraints = [
            models.UniqueConstraint(
                fields=["opportunity", "applicant"], name="uniq_application_per_opportunity"
            )
        ]
        indexes = [
            models.Index(fields=["applicant", "-created_at"]),
            models.Index(fields=["opportunity", "status", "submitted_at"]),
        ]


class ApplicationStatusChange(UUIDModel):
    """Immutable history: who moved an application from what to what, and why."""

    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="history"
    )
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reason = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "application_status_changes"
        ordering = ["created_at"]


class Booking(TimeStampedModel):
    """Performer selection. Created in the same transaction that accepts an application;
    booking outcomes (completed, no-show, cancelled) are tracked separately from the
    application decision."""

    class Status(models.TextChoices):
        CONFIRMED = "confirmed"
        CANCELLED = "cancelled"
        COMPLETED = "completed"
        NO_SHOW = "no_show"

    ACTIVE_STATUSES = (Status.CONFIRMED, Status.COMPLETED)

    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.PROTECT, related_name="bookings"
    )
    application = models.OneToOneField(
        Application, on_delete=models.PROTECT, related_name="booking"
    )
    performer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    selected_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="+",
    )
    cancellation_reason = models.TextField(max_length=2000, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "performer_selections"
        indexes = [
            models.Index(fields=["opportunity", "status"]),
            models.Index(fields=["performer", "-created_at"]),
        ]

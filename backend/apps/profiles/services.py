"""Profiles domain: profile visibility, editing, portfolio, venues."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.identity import services as identity
from apps.identity.models import Role
from apps.media import services as media
from apps.outbox import services as outbox
from apps.trust_safety import services as safety
from shared.errors import Conflict, Forbidden, NotFound, ValidationFailed

from .models import (
    ArtistDetails,
    Genre,
    OrganizerDetails,
    PortfolioItem,
    Profile,
    Skill,
    Venue,
    VenueBooking,
    VenueMembership,
    Visibility,
)

MAX_PORTFOLIO_ITEMS = 30


def create_profile_for_user(user):
    profile = Profile.objects.create(user=user, display_name=user.display_name)
    return profile


def get_own_profile(user):
    return Profile.objects.select_related("artist", "organizer").get(user=user)


def visible_profiles(viewer):
    qs = Profile.objects.filter(user__is_active=True)
    if viewer is None or not viewer.is_authenticated:
        return qs.filter(visibility=Visibility.PUBLIC)
    qs = qs.filter(Q(visibility__in=[Visibility.PUBLIC, Visibility.MEMBERS]) | Q(user=viewer))
    return safety.exclude_blocked(qs, viewer, "user")


def get_visible_profile(viewer, profile_id):
    profile = (
        visible_profiles(viewer)
        .select_related("user", "artist", "organizer")
        .filter(id=profile_id)
        .first()
    )
    if profile is None:
        raise NotFound("Profile not found.")
    return profile


def search_profiles(viewer, *, q=None, genre=None, skill=None, location=None, role=None):
    qs = visible_profiles(viewer).select_related("artist", "organizer")
    if q:
        qs = qs.filter(
            Q(display_name__icontains=q)
            | Q(headline__icontains=q)
            | Q(artist__artist_name__icontains=q)
        )
    if genre:
        qs = qs.filter(artist__genres__slug=genre)
    if skill:
        qs = qs.filter(artist__skills__slug=skill)
    if location:
        qs = qs.filter(location_label__icontains=location)
    if role == Role.ARTIST:
        qs = qs.filter(user__role_assignments__role=Role.ARTIST)
    elif role == Role.ORGANIZER:
        qs = qs.filter(user__role_assignments__role=Role.ORGANIZER)
    return qs.distinct()


def _slugs_to(model, slugs, field):
    objs = list(model.objects.filter(slug__in=slugs))
    if len(objs) != len(set(slugs)):
        raise ValidationFailed(details={"fields": {field: ["Unknown value."]}})
    return objs


@transaction.atomic
def update_own_profile(user, *, core=None, artist=None, organizer=None):
    profile = Profile.objects.select_for_update().get(user=user)
    for field, value in (core or {}).items():
        setattr(profile, field, value)
    profile.save()

    if artist is not None:
        if not identity.has_role(user, Role.ARTIST):
            raise Forbidden("Add the artist role to edit artist details.", code="role_required")
        details, _ = ArtistDetails.objects.get_or_create(profile=profile)
        genres = artist.pop("genres", None)
        skills = artist.pop("skills", None)
        for field, value in artist.items():
            setattr(details, field, value)
        details.save()
        if genres is not None:
            details.genres.set(_slugs_to(Genre, genres, "genres"))
        if skills is not None:
            details.skills.set(_slugs_to(Skill, skills, "skills"))

    if organizer is not None:
        if not identity.has_role(user, Role.ORGANIZER):
            raise Forbidden("Add the organizer role to edit organizer details.",
                            code="role_required")
        details, _ = OrganizerDetails.objects.get_or_create(profile=profile)
        for field, value in organizer.items():
            setattr(details, field, value)
        details.save()
    return get_own_profile(user)


def add_portfolio_item(user, data):
    profile = get_own_profile(user)
    if profile.portfolio.count() >= MAX_PORTFOLIO_ITEMS:
        raise ValidationFailed(f"A portfolio can hold at most {MAX_PORTFOLIO_ITEMS} items.")
    return PortfolioItem.objects.create(profile=profile, **data)


def get_own_portfolio_item(user, item_id):
    item = PortfolioItem.objects.filter(id=item_id, profile__user=user).first()
    if item is None:
        raise NotFound("Portfolio item not found.")
    return item


def own_portfolio_items(user, item_ids):
    """Validate that every referenced portfolio item belongs to `user` (used by applications)."""
    items = list(PortfolioItem.objects.filter(id__in=item_ids, profile__user=user))
    if len(items) != len(set(item_ids)):
        raise ValidationFailed(details={"fields": {"portfolio_item_ids": ["Unknown item."]}})
    return items


# --- Venues -----------------------------------------------------------------

def is_venue_manager(user, venue_id):
    if not user or not user.is_authenticated or venue_id is None:
        return False
    return VenueMembership.objects.filter(venue_id=venue_id, user=user).exists()


def managed_venue_ids(user):
    return VenueMembership.objects.filter(user=user).values("venue_id")


def get_venue(venue_id):
    venue = Venue.objects.filter(id=venue_id).first()
    if venue is None:
        raise NotFound("Venue not found.")
    return venue


MAX_VENUE_PHOTOS = 8
BOOKING_HORIZON_DAYS = 365


def listed_venues():
    return (Venue.objects.filter(is_listed=True)
            .prefetch_related("photos", "memberships__user__profile"))


def _set_photos(actor, venue, photo_ids):
    if photo_ids is not None:
        venue.photos.set(media.owned_assets(actor, photo_ids, limit=MAX_VENUE_PHOTOS))


@transaction.atomic
def create_venue(actor, data):
    if not (identity.has_role(actor, Role.VENUE) or identity.has_role(actor, Role.ORGANIZER)):
        raise Forbidden("Add the venue role to list a venue.", code="role_required")
    photo_ids = data.pop("photo_ids", None)
    venue = Venue.objects.create(created_by=actor, **data)
    VenueMembership.objects.create(venue=venue, user=actor)
    _set_photos(actor, venue, photo_ids)
    audit.record(actor=actor, action="venue.created", resource=venue)
    return venue


@transaction.atomic
def update_venue(actor, venue, data):
    if not is_venue_manager(actor, venue.id):
        raise Forbidden()
    photo_ids = data.pop("photo_ids", None)
    for field, value in data.items():
        setattr(venue, field, value)
    venue.save()
    _set_photos(actor, venue, photo_ids)
    return venue


@transaction.atomic
def add_venue_manager(actor, venue, user):
    if not is_venue_manager(actor, venue.id):
        raise Forbidden()
    _, created = VenueMembership.objects.get_or_create(venue=venue, user=user)
    if created:
        audit.record(
            actor=actor, action="venue.manager_added", resource=venue,
            metadata={"user_id": str(user.id)},
        )
    return created


# --- Venue bookings ---------------------------------------------------------


def _manager_ids(venue):
    return [str(i) for i in venue.memberships.values_list("user_id", flat=True)]


def _check_bookable_date(date):
    today = timezone.localdate()
    if date < today:
        raise ValidationFailed("Pick a date from today onwards.",
                               details={"fields": {"date": ["That date has passed."]}})
    if date > today + timedelta(days=BOOKING_HORIZON_DAYS):
        raise ValidationFailed("Bookings open up to a year ahead.",
                               details={"fields": {"date": ["Too far ahead."]}})


def _date_taken(venue, date, exclude_id=None):
    qs = VenueBooking.objects.filter(venue=venue, date=date, status__in=VenueBooking.TAKEN)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def _event(booking, event, **extra):
    outbox.publish(f"venue_booking.{event}", {
        "booking_id": str(booking.id), "venue_id": str(booking.venue_id),
        "venue_name": booking.venue.name, "date": booking.date.isoformat(),
        "requester_id": str(booking.requester_id), "manager_ids": _manager_ids(booking.venue),
        **extra,
    })


def availability(viewer, venue, start, days):
    """Dates in [start, start+days) that are not simply free. The public sees taken dates;
    a requester also sees their own open requests; managers see where requests wait."""
    end = start + timedelta(days=days - 1)
    manager = is_venue_manager(viewer, venue.id)
    viewer_id = viewer.id if viewer is not None and viewer.is_authenticated else None
    marks = {}
    rows = venue.bookings.filter(date__range=(start, end)).exclude(
        status__in=[VenueBooking.Status.DECLINED, VenueBooking.Status.CANCELLED])
    for b in rows:
        if b.status in VenueBooking.TAKEN:
            marks[b.date] = "booked" if b.status == VenueBooking.Status.CONFIRMED else "blocked"
        elif b.requester_id == viewer_id:
            marks.setdefault(b.date, "requested_by_you")
        elif manager:
            marks.setdefault(b.date, "has_requests")
    return {"start": start, "end": end,
            "days": [{"date": d, "status": marks[d]} for d in sorted(marks)]}


@transaction.atomic
def request_booking(actor, venue, *, date, message="", expected_headcount=None):
    if not venue.is_listed:
        raise NotFound("Venue not found.")
    if is_venue_manager(actor, venue.id):
        raise Conflict("You manage this venue. Block the date instead.", code="own_venue")
    _check_bookable_date(date)
    if _date_taken(venue, date):
        raise Conflict("That date is already booked. Pick another day.", code="date_unavailable")
    try:
        with transaction.atomic():
            booking = VenueBooking.objects.create(
                venue=venue, requester=actor, date=date, message=message.strip(),
                expected_headcount=expected_headcount,
            )
    except IntegrityError as exc:
        raise Conflict("You already asked for this date.", code="already_requested") from exc
    audit.record(actor=actor, action="venue_booking.requested", resource=booking)
    _event(booking, "requested")
    return booking


def _lock_venue(venue_id):
    # Lock order is always venue, then bookings. Locking the booking first deadlocks:
    # two confirms each hold their own request and wait on the other's while declining
    # rivals. One lock per venue makes every booking change for it take turns.
    Venue.objects.select_for_update().filter(id=venue_id).first()


def _locked_booking(booking_id):
    venue_id = VenueBooking.objects.filter(id=booking_id).values_list("venue_id", flat=True).first()
    if venue_id is None:
        raise NotFound("Booking not found.")
    _lock_venue(venue_id)
    return VenueBooking.objects.select_for_update().select_related("venue").get(id=booking_id)


def _take_date(actor, booking, status):
    """Confirm or block `booking`'s date. The caller holds the venue lock; the unique
    constraint backs it up. Competing open requests for that day are declined."""
    if _date_taken(booking.venue, booking.date, exclude_id=booking.id):
        raise Conflict("That date is already booked.", code="date_unavailable")
    booking.status, booking.decided_by, booking.decided_at = status, actor, timezone.now()
    try:
        with transaction.atomic():
            booking.save()
    except IntegrityError as exc:
        raise Conflict("That date is already booked.", code="date_unavailable") from exc
    losers = VenueBooking.objects.select_for_update().filter(
        venue_id=booking.venue_id, date=booking.date, status=VenueBooking.Status.REQUESTED,
    ).exclude(id=booking.id).select_related("venue")
    for other in losers:
        other.status, other.decided_by, other.decided_at = (
            VenueBooking.Status.DECLINED, actor, timezone.now())
        other.save()
        _event(other, "status_changed", to_status="declined", actor_id=str(actor.id))


@transaction.atomic
def decide_booking(actor, booking_id, to):
    booking = _locked_booking(booking_id)
    if not is_venue_manager(actor, booking.venue_id):
        raise NotFound("Booking not found.")
    if booking.status != VenueBooking.Status.REQUESTED:
        raise Conflict(f"This request is already {booking.status}.", code="invalid_transition")
    if to == VenueBooking.Status.CONFIRMED:
        _check_bookable_date(booking.date)
        _take_date(actor, booking, VenueBooking.Status.CONFIRMED)
    else:
        booking.status, booking.decided_by, booking.decided_at = to, actor, timezone.now()
        booking.save()
    audit.record(actor=actor, action=f"venue_booking.{to}", resource=booking)
    _event(booking, "status_changed", to_status=to, actor_id=str(actor.id))
    return booking


@transaction.atomic
def cancel_booking(actor, booking_id):
    booking = _locked_booking(booking_id)
    manager = is_venue_manager(actor, booking.venue_id)
    if not manager and booking.requester_id != actor.id:
        raise NotFound("Booking not found.")
    cancellable = {VenueBooking.Status.REQUESTED, VenueBooking.Status.CONFIRMED}
    if manager:
        cancellable.add(VenueBooking.Status.BLOCKED)
    if booking.status not in cancellable:
        raise Conflict(f"A {booking.status} booking can't be cancelled.", code="invalid_transition")
    was_blocked = booking.status == VenueBooking.Status.BLOCKED
    booking.status, booking.decided_by, booking.decided_at = (
        VenueBooking.Status.CANCELLED, actor, timezone.now())
    booking.save()
    audit.record(actor=actor, action="venue_booking.cancelled", resource=booking)
    if not was_blocked:
        _event(booking, "status_changed", to_status="cancelled", actor_id=str(actor.id))
    return booking


@transaction.atomic
def block_date(actor, venue, *, date, message=""):
    if not is_venue_manager(actor, venue.id):
        raise Forbidden()
    _check_bookable_date(date)
    _lock_venue(venue.id)
    booking = VenueBooking(venue=venue, requester=actor, date=date, message=message.strip())
    _take_date(actor, booking, VenueBooking.Status.BLOCKED)
    audit.record(actor=actor, action="venue_booking.blocked", resource=booking)
    return booking


def venue_bookings_for_manager(actor, venue):
    if not is_venue_manager(actor, venue.id):
        raise Forbidden()
    since = timezone.localdate() - timedelta(days=30)
    return (venue.bookings.filter(date__gte=since).select_related("venue", "requester__profile")
            .order_by("date", "created_at"))


def my_venue_bookings(actor):
    return (VenueBooking.objects.filter(requester=actor).exclude(status=VenueBooking.Status.BLOCKED)
            .select_related("venue", "requester__profile").order_by("-date"))

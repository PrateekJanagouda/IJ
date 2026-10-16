"""Opportunities domain: events, opportunities, applications and bookings.

Rules of the road:
- Every write checks authorization here, not in views or the frontend.
- State changes go through explicit transitions; illegal transitions raise Conflict.
- Consequential writes lock rows in a fixed order (opportunity -> application) to avoid
  deadlocks, record history + audit, and publish an outbox event in the same transaction.
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.audit import services as audit
from apps.identity import services as identity
from apps.identity.models import Role
from apps.outbox import services as outbox
from apps.profiles import services as profiles
from apps.profiles.models import Genre, Skill
from apps.trust_safety import services as safety
from shared.errors import Conflict, Forbidden, NotFound, ValidationFailed

from .models import Application, ApplicationStatusChange, Booking, Event, Opportunity

AppStatus = Application.Status
OppStatus = Opportunity.Status
EventStatus = Event.Status

# --- Policies ---------------------------------------------------------------


def can_manage_event(user, event):
    if not user or not user.is_authenticated:
        return False
    return event.owner_id == user.id or profiles.is_venue_manager(user, event.venue_id)


def can_manage_opportunity(user, opportunity):
    if not user or not user.is_authenticated:
        return False
    if opportunity.owner_id == user.id:
        return True
    return opportunity.event_id is not None and can_manage_event(user, opportunity.event)


def _require_organizer(user):
    if not identity.has_role(user, Role.ORGANIZER):
        raise Forbidden("The organizer role is required.", code="role_required")


def accepting_applications(opportunity, now=None):
    now = now or timezone.now()
    if opportunity.status != OppStatus.PUBLISHED:
        return False
    if opportunity.application_deadline and opportunity.application_deadline <= now:
        return False
    return not (opportunity.event_id and opportunity.event.status != EventStatus.PUBLISHED)


# --- Events -----------------------------------------------------------------


def _validate_times(starts_at, ends_at):
    if starts_at and ends_at and ends_at < starts_at:
        raise ValidationFailed(details={"fields": {"ends_at": ["Must be after starts_at."]}})


@transaction.atomic
def create_event(actor, data):
    _require_organizer(actor)
    venue = data.pop("venue", None)
    if venue is not None and not profiles.is_venue_manager(actor, venue.id):
        raise Forbidden("Only managers of this venue can attach events to it.")
    _validate_times(data.get("starts_at"), data.get("ends_at"))
    event = Event.objects.create(owner=actor, venue=venue, **data)
    audit.record(actor=actor, action="event.created", resource=event)
    return event


def _lock_event(event_id):
    event = Event.objects.select_for_update().filter(id=event_id).first()
    if event is None:
        raise NotFound("Event not found.")
    return event


def _require_event_manager(actor, event):
    if not can_manage_event(actor, event):
        # Do not reveal drafts to non-managers.
        if event.status == EventStatus.DRAFT:
            raise NotFound("Event not found.")
        raise Forbidden()


@transaction.atomic
def update_event(actor, event_id, data):
    event = _lock_event(event_id)
    _require_event_manager(actor, event)
    if event.status not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
        raise Conflict("Cancelled or completed events cannot be edited.", code="event_not_editable")
    if "venue" in data:
        venue = data.pop("venue")
        if venue is not None and not profiles.is_venue_manager(actor, venue.id):
            raise Forbidden("Only managers of this venue can attach events to it.")
        event.venue = venue
    for field, value in data.items():
        setattr(event, field, value)
    _validate_times(event.starts_at, event.ends_at)
    event.save()
    return event


@transaction.atomic
def publish_event(actor, event_id):
    event = _lock_event(event_id)
    _require_event_manager(actor, event)
    if event.status == EventStatus.PUBLISHED:
        return event
    if event.status != EventStatus.DRAFT:
        raise Conflict("Only draft events can be published.", code="invalid_transition")
    missing = [f for f in ("title", "starts_at") if not getattr(event, f)]
    if not (event.location_text or event.venue_id or event.is_online):
        missing.append("location_text")
    if missing:
        raise ValidationFailed(
            "The event is incomplete.", code="listing_incomplete",
            details={"fields": {f: ["Required to publish."] for f in missing}},
        )
    event.status = EventStatus.PUBLISHED
    event.published_at = timezone.now()
    event.save(update_fields=["status", "published_at", "updated_at"])
    audit.record(actor=actor, action="event.published", resource=event)
    outbox.publish("event.published", {"event_id": str(event.id), "owner_id": str(event.owner_id)})
    return event


@transaction.atomic
def cancel_event(actor, event_id, *, reason="", confirm=False):
    """Cancel an event. Child opportunities are NOT cascaded (manual review policy):
    the organizer resolves each one. New applications to them are refused immediately."""
    event = _lock_event(event_id)
    _require_event_manager(actor, event)
    if event.status == EventStatus.CANCELLED:
        return event
    if event.status not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
        raise Conflict("This event can no longer be cancelled.", code="invalid_transition")
    performer_ids = list(
        Booking.objects.filter(
            opportunity__event=event, status=Booking.Status.CONFIRMED
        ).values_list("performer_id", flat=True)
    )
    if performer_ids and not confirm:
        raise Conflict(
            "This event has confirmed performers. Resubmit with confirm=true to cancel.",
            code="confirmation_required",
            details={"confirmed_bookings": len(performer_ids)},
        )
    event.status = EventStatus.CANCELLED
    event.cancelled_at = timezone.now()
    event.cancelled_by = actor
    event.cancellation_reason = reason
    event.save()
    audit.record(
        actor=actor, action="event.cancelled", resource=event,
        metadata={"confirmed_bookings": len(performer_ids)},
    )
    outbox.publish(
        "event.cancelled",
        {
            "event_id": str(event.id),
            "actor_id": str(actor.id),
            "title": event.title,
            "performer_ids": sorted({str(p) for p in performer_ids}),
        },
    )
    return event


@transaction.atomic
def complete_event(actor, event_id):
    event = _lock_event(event_id)
    _require_event_manager(actor, event)
    if event.status != EventStatus.PUBLISHED:
        raise Conflict("Only published events can be completed.", code="invalid_transition")
    event.status = EventStatus.COMPLETED
    event.save(update_fields=["status", "updated_at"])
    audit.record(actor=actor, action="event.completed", resource=event)
    return event


def visible_events(viewer):
    qs = Event.objects.select_related("venue")
    public = ~Q(status=EventStatus.DRAFT)
    if viewer is not None and viewer.is_authenticated:
        managed = Q(owner=viewer) | Q(venue__in=profiles.managed_venue_ids(viewer))
        qs = qs.filter(public | managed)
        return safety.exclude_blocked(qs, viewer, "owner")
    return qs.filter(public)


def get_visible_event(viewer, event_id):
    event = visible_events(viewer).filter(id=event_id).first()
    if event is None:
        raise NotFound("Event not found.")
    return event


def discover_events(viewer, *, q=None, starts_after=None, starts_before=None, location=None):
    qs = visible_events(viewer).filter(
        status=EventStatus.PUBLISHED, visibility=Event.Visibility.PUBLIC
    )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if starts_after:
        qs = qs.filter(starts_at__gte=starts_after)
    if starts_before:
        qs = qs.filter(starts_at__lte=starts_before)
    if location:
        qs = qs.filter(Q(location_text__icontains=location) | Q(venue__city__icontains=location))
    return qs


def managed_events(user):
    return Event.objects.select_related("venue").filter(
        Q(owner=user) | Q(venue__in=profiles.managed_venue_ids(user))
    )


def event_opportunities(viewer, event):
    qs = Opportunity.objects.filter(event=event).select_related("event")
    if not can_manage_event(viewer, event):
        qs = qs.exclude(status=OppStatus.DRAFT)
    return qs.order_by("starts_at", "created_at")


def event_lineup(viewer, event):
    if not can_manage_event(viewer, event):
        raise Forbidden()
    return (
        Booking.objects.filter(opportunity__event=event, status__in=Booking.ACTIVE_STATUSES)
        .select_related("performer", "performer__profile", "opportunity")
        .order_by("opportunity__starts_at", "selected_at")
    )


# --- Opportunities ----------------------------------------------------------


def _set_taxonomy(opportunity, genres, skills):
    if genres is not None:
        found = list(Genre.objects.filter(slug__in=genres))
        if len(found) != len(set(genres)):
            raise ValidationFailed(details={"fields": {"genres": ["Unknown genre."]}})
        opportunity.genres.set(found)
    if skills is not None:
        found = list(Skill.objects.filter(slug__in=skills))
        if len(found) != len(set(skills)):
            raise ValidationFailed(details={"fields": {"skills": ["Unknown skill."]}})
        opportunity.skills.set(found)


def _validate_compensation(opp):
    if opp.compensation_amount is not None and not opp.currency:
        raise ValidationFailed(details={"fields": {"currency": ["Required with an amount."]}})


@transaction.atomic
def create_opportunity(actor, data):
    _require_organizer(actor)
    genres, skills = data.pop("genres", None), data.pop("skills", None)
    event = data.pop("event", None)
    if event is not None:
        event = _lock_event(event.id)
        _require_event_manager(actor, event)
        if event.status not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
            raise Conflict("Cannot add slots to a cancelled or completed event.",
                           code="event_not_editable")
    opp = Opportunity(owner=actor, event=event, **data)
    _validate_times(opp.starts_at, opp.ends_at)
    _validate_compensation(opp)
    opp.save()
    _set_taxonomy(opp, genres, skills)
    audit.record(actor=actor, action="opportunity.created", resource=opp)
    return opp


def _lock_opportunity(opportunity_id):
    opp = (
        Opportunity.objects.select_for_update(of=("self",))
        .select_related("event")
        .filter(id=opportunity_id)
        .first()
    )
    if opp is None:
        raise NotFound("Opportunity not found.")
    return opp


def _require_opportunity_manager(actor, opp):
    if not can_manage_opportunity(actor, opp):
        if opp.status == OppStatus.DRAFT:
            raise NotFound("Opportunity not found.")
        raise Forbidden()


PUBLISHED_EDITABLE = {
    "description", "requirements", "application_deadline", "capacity", "location_text",
    "is_online", "starts_at", "ends_at", "timezone", "genres", "skills",
}


@transaction.atomic
def update_opportunity(actor, opportunity_id, data):
    opp = _lock_opportunity(opportunity_id)
    _require_opportunity_manager(actor, opp)
    if opp.status in (OppStatus.CANCELLED, OppStatus.COMPLETED):
        raise Conflict("This opportunity can no longer be edited.", code="not_editable")
    if opp.status != OppStatus.DRAFT:
        locked = set(data) - PUBLISHED_EDITABLE
        if locked:
            raise Conflict(
                "These fields cannot change after publication.", code="field_locked",
                details={"fields": sorted(locked)},
            )
    genres, skills = data.pop("genres", None), data.pop("skills", None)
    if "capacity" in data:
        active = opp.bookings.filter(status__in=Booking.ACTIVE_STATUSES).count()
        if data["capacity"] < active:
            raise Conflict("Capacity cannot be below confirmed bookings.", code="capacity_conflict")
    for field, value in data.items():
        setattr(opp, field, value)
    _validate_times(opp.starts_at, opp.ends_at)
    _validate_compensation(opp)
    opp.save()
    _set_taxonomy(opp, genres, skills)
    return opp


@transaction.atomic
def publish_opportunity(actor, opportunity_id):
    opp = _lock_opportunity(opportunity_id)
    _require_opportunity_manager(actor, opp)
    if opp.status == OppStatus.PUBLISHED:
        return opp
    if opp.status not in (OppStatus.DRAFT, OppStatus.CLOSED):
        raise Conflict("This opportunity cannot be published.", code="invalid_transition")
    missing = [f for f in ("title", "description", "opportunity_type", "compensation_type")
               if not getattr(opp, f)]
    if not (opp.location_text or opp.is_online or opp.event_id):
        missing.append("location_text")
    if missing:
        raise ValidationFailed(
            "The listing is incomplete.", code="listing_incomplete",
            details={"fields": {f: ["Required to publish."] for f in missing}},
        )
    if opp.application_deadline and opp.application_deadline <= timezone.now():
        raise ValidationFailed(
            code="listing_incomplete",
            details={"fields": {"application_deadline": ["Must be in the future."]}},
        )
    if opp.event_id and opp.event.status != EventStatus.PUBLISHED:
        raise Conflict("Publish the parent event first.", code="event_not_published")
    first_publish = opp.published_at is None
    opp.status = OppStatus.PUBLISHED
    opp.published_at = opp.published_at or timezone.now()
    opp.save(update_fields=["status", "published_at", "updated_at"])
    audit.record(actor=actor, action="opportunity.published", resource=opp)
    if first_publish:
        outbox.publish("opportunity.published", {"opportunity_id": str(opp.id)})
    return opp


@transaction.atomic
def close_opportunity(actor, opportunity_id):
    opp = _lock_opportunity(opportunity_id)
    _require_opportunity_manager(actor, opp)
    if opp.status == OppStatus.CLOSED:
        return opp
    if opp.status != OppStatus.PUBLISHED:
        raise Conflict("Only published opportunities can be closed.", code="invalid_transition")
    opp.status = OppStatus.CLOSED
    opp.save(update_fields=["status", "updated_at"])
    audit.record(actor=actor, action="opportunity.closed", resource=opp)
    return opp


@transaction.atomic
def complete_opportunity(actor, opportunity_id):
    opp = _lock_opportunity(opportunity_id)
    _require_opportunity_manager(actor, opp)
    if opp.status not in (OppStatus.PUBLISHED, OppStatus.CLOSED):
        raise Conflict("Only live opportunities can be completed.", code="invalid_transition")
    opp.status = OppStatus.COMPLETED
    opp.save(update_fields=["status", "updated_at"])
    audit.record(actor=actor, action="opportunity.completed", resource=opp)
    return opp


@transaction.atomic
def cancel_opportunity(actor, opportunity_id, *, reason="", confirm=False):
    opp = _lock_opportunity(opportunity_id)
    _require_opportunity_manager(actor, opp)
    if opp.status == OppStatus.CANCELLED:
        return opp
    if opp.status == OppStatus.COMPLETED:
        raise Conflict("Completed opportunities cannot be cancelled.", code="invalid_transition")
    confirmed = list(opp.bookings.select_for_update().filter(status=Booking.Status.CONFIRMED))
    if confirmed and not confirm:
        raise Conflict(
            "This opportunity has confirmed performers. Resubmit with confirm=true to cancel.",
            code="confirmation_required",
            details={"confirmed_bookings": len(confirmed)},
        )
    now = timezone.now()
    for booking in confirmed:
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = now
        booking.cancelled_by = actor
        booking.cancellation_reason = "opportunity_cancelled"
        booking.save()
    opp.status = OppStatus.CANCELLED
    opp.cancelled_at = now
    opp.cancellation_reason = reason
    opp.save()
    recipients = opp.applications.filter(
        status__in=[AppStatus.SUBMITTED, AppStatus.SHORTLISTED, AppStatus.ACCEPTED]
    ).values_list("applicant_id", flat=True)
    audit.record(
        actor=actor, action="opportunity.cancelled", resource=opp,
        metadata={"cancelled_bookings": len(confirmed)},
    )
    outbox.publish(
        "opportunity.cancelled",
        {
            "opportunity_id": str(opp.id),
            "actor_id": str(actor.id),
            "title": opp.title,
            "recipient_ids": sorted(str(r) for r in recipients),
        },
    )
    return opp


@transaction.atomic
def moderate_close_opportunity(moderator, opportunity_id):
    """Trust & safety entry point: close a listing regardless of ownership (audited)."""
    opp = _lock_opportunity(opportunity_id)
    if opp.status in (OppStatus.PUBLISHED, OppStatus.DRAFT):
        opp.status = OppStatus.CLOSED
        opp.save(update_fields=["status", "updated_at"])
    audit.record(actor=moderator, action="moderation.opportunity_closed", resource=opp)
    return opp


def visible_opportunities(viewer):
    qs = Opportunity.objects.select_related("event", "owner").prefetch_related("genres", "skills")
    public = ~Q(status=OppStatus.DRAFT)
    if viewer is not None and viewer.is_authenticated:
        managed = (
            Q(owner=viewer)
            | Q(event__owner=viewer)
            | Q(event__venue__in=profiles.managed_venue_ids(viewer))
        )
        return safety.exclude_blocked(qs.filter(public | managed), viewer, "owner")
    return qs.filter(public)


def get_visible_opportunity(viewer, opportunity_id):
    opp = visible_opportunities(viewer).filter(id=opportunity_id).first()
    if opp is None:
        raise NotFound("Opportunity not found.")
    return opp


def discover_opportunities(
    viewer, *, q=None, opportunity_type=None, compensation_type=None, genre=None, skill=None,
    location=None, starts_after=None, starts_before=None, event_id=None, include_closed=False,
):
    """Public discovery: published listings whose parent event (if any) is public."""
    now = timezone.now()
    qs = visible_opportunities(viewer).filter(
        Q(event__isnull=True)
        | Q(event__status=EventStatus.PUBLISHED, event__visibility=Event.Visibility.PUBLIC)
    )
    if include_closed:
        qs = qs.filter(status__in=[OppStatus.PUBLISHED, OppStatus.CLOSED])
    else:
        qs = qs.filter(status=OppStatus.PUBLISHED).filter(
            Q(application_deadline__isnull=True) | Q(application_deadline__gt=now)
        )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if opportunity_type:
        qs = qs.filter(opportunity_type=opportunity_type)
    if compensation_type:
        qs = qs.filter(compensation_type=compensation_type)
    if genre:
        qs = qs.filter(genres__slug=genre)
    if skill:
        qs = qs.filter(skills__slug=skill)
    if location:
        qs = qs.filter(
            Q(location_text__icontains=location)
            | Q(event__location_text__icontains=location)
            | Q(event__venue__city__icontains=location)
        )
    if starts_after:
        qs = qs.filter(starts_at__gte=starts_after)
    if starts_before:
        qs = qs.filter(starts_at__lte=starts_before)
    if event_id:
        qs = qs.filter(event_id=event_id)
    return qs.distinct()


def managed_opportunities(user):
    return (
        Opportunity.objects.select_related("event")
        .prefetch_related("genres", "skills")
        .filter(
            Q(owner=user)
            | Q(event__owner=user)
            | Q(event__venue__in=profiles.managed_venue_ids(user))
        )
        .annotate(
            application_count=Count("applications", distinct=True),
        )
    )


def active_booking_count(opportunity):
    return opportunity.bookings.filter(status__in=Booking.ACTIVE_STATUSES).count()


# --- Applications -----------------------------------------------------------


@transaction.atomic
def submit_application(actor, opportunity_id, *, cover_note="", portfolio_item_ids=()):
    if not identity.has_role(actor, Role.ARTIST):
        raise Forbidden("The artist role is required to apply.", code="role_required")
    opp = get_visible_opportunity(actor, opportunity_id)
    if opp.owner_id == actor.id or can_manage_opportunity(actor, opp):
        raise Conflict("You cannot apply to an opportunity you manage.", code="own_opportunity")
    if not accepting_applications(opp):
        raise Conflict("This opportunity is not accepting applications.",
                       code="application_not_open")
    if safety.is_blocked(actor.id, opp.owner_id):
        raise NotFound("Opportunity not found.")
    items = profiles.own_portfolio_items(actor, list(portfolio_item_ids))
    if Application.objects.filter(opportunity=opp, applicant=actor).exists():
        raise Conflict("You have already applied to this opportunity.", code="already_applied")
    try:
        with transaction.atomic():
            application = Application.objects.create(
                opportunity=opp, applicant=actor, cover_note=cover_note
            )
    except IntegrityError as exc:  # lost a race with a concurrent submit: same answer
        raise Conflict("You have already applied to this opportunity.",
                       code="already_applied") from exc
    application.portfolio_items.set(items)
    ApplicationStatusChange.objects.create(
        application=application, from_status="", to_status=AppStatus.SUBMITTED, actor=actor
    )
    audit.record(actor=actor, action="application.submitted", resource=application)
    outbox.publish(
        "application.submitted",
        {
            "application_id": str(application.id),
            "opportunity_id": str(opp.id),
            "opportunity_title": opp.title,
            "applicant_id": str(actor.id),
            "owner_id": str(opp.owner_id),
        },
    )
    return application


def _lock_application(application_id):
    """Lock opportunity first, then the application (consistent order avoids deadlocks)."""
    opportunity_id = (
        Application.objects.filter(id=application_id).values_list("opportunity_id", flat=True)
        .first()
    )
    if opportunity_id is None:
        raise NotFound("Application not found.")
    opp = _lock_opportunity(opportunity_id)
    application = Application.objects.select_for_update().get(id=application_id)
    application.opportunity = opp
    return opp, application


ORGANIZER_TRANSITIONS = {
    AppStatus.SUBMITTED: {AppStatus.SHORTLISTED, AppStatus.ACCEPTED, AppStatus.DECLINED},
    AppStatus.SHORTLISTED: {AppStatus.ACCEPTED, AppStatus.DECLINED},
}
APPLICANT_TRANSITIONS = {
    AppStatus.SUBMITTED: {AppStatus.WITHDRAWN},
    AppStatus.SHORTLISTED: {AppStatus.WITHDRAWN},
}


def _record_transition(application, actor, to_status, reason):
    from_status = application.status
    application.status = to_status
    if to_status in (AppStatus.ACCEPTED, AppStatus.DECLINED):
        application.decided_at = timezone.now()
        application.decided_by = actor
    application.save()
    ApplicationStatusChange.objects.create(
        application=application, from_status=from_status, to_status=to_status,
        actor=actor, reason=reason,
    )
    audit.record(
        actor=actor, action=f"application.{to_status}", resource=application,
        metadata={"from": from_status},
    )
    outbox.publish(
        "application.status_changed",
        {
            "application_id": str(application.id),
            "opportunity_id": str(application.opportunity_id),
            "opportunity_title": application.opportunity.title,
            "applicant_id": str(application.applicant_id),
            "owner_id": str(application.opportunity.owner_id),
            "actor_id": str(actor.id),
            "from_status": from_status,
            "to_status": to_status,
        },
    )


@transaction.atomic
def transition_application(actor, application_id, to_status, *, reason=""):
    opp, application = _lock_application(application_id)
    is_manager = can_manage_opportunity(actor, opp)
    is_applicant = application.applicant_id == actor.id
    if not (is_manager or is_applicant):
        raise NotFound("Application not found.")

    # Idempotency: repeating the same decision (e.g. a client retry) is a no-op.
    if application.status == to_status:
        return application

    if to_status == AppStatus.WITHDRAWN:
        if not is_applicant:
            raise Forbidden("Only the applicant can withdraw.")
        allowed = APPLICANT_TRANSITIONS.get(application.status, set())
    else:
        if not is_manager:
            raise Forbidden("Only the opportunity's managers can change this status.")
        allowed = ORGANIZER_TRANSITIONS.get(application.status, set())
    if to_status not in allowed:
        raise Conflict(
            f"Cannot move an application from {application.status} to {to_status}.",
            code="invalid_transition",
        )
    if to_status != AppStatus.WITHDRAWN and opp.status not in (
        OppStatus.PUBLISHED, OppStatus.CLOSED
    ):
        raise Conflict("This opportunity is no longer active.", code="opportunity_inactive")

    if to_status == AppStatus.ACCEPTED:
        # The opportunity row is locked, so concurrent acceptances serialize here and the
        # count below cannot be stale. A unique constraint alone could not enforce this.
        if active_booking_count(opp) >= opp.capacity:
            raise Conflict("All places for this opportunity are filled.", code="capacity_full")
        _record_transition(application, actor, to_status, reason)
        Booking.objects.create(
            opportunity=opp, application=application, performer_id=application.applicant_id,
            selected_by=actor,
        )
    else:
        _record_transition(application, actor, to_status, reason)
    return application


def get_application(viewer, application_id):
    application = (
        Application.objects.select_related(
            "opportunity", "opportunity__event", "applicant", "applicant__profile"
        )
        .prefetch_related("portfolio_items")
        .filter(id=application_id)
        .first()
    )
    if application is None or not (
        application.applicant_id == viewer.id
        or can_manage_opportunity(viewer, application.opportunity)
    ):
        raise NotFound("Application not found.")
    return application


def applications_for_opportunity(viewer, opportunity_id, status=None):
    opp = get_visible_opportunity(viewer, opportunity_id)
    if not can_manage_opportunity(viewer, opp):
        raise Forbidden()
    qs = (
        Application.objects.filter(opportunity=opp)
        .select_related("applicant", "applicant__profile", "opportunity")
        .prefetch_related("portfolio_items")
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def my_applications(user, status=None):
    qs = Application.objects.filter(applicant=user).select_related(
        "opportunity", "opportunity__event", "applicant", "applicant__profile"
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def application_history(viewer, application_id):
    application = get_application(viewer, application_id)
    return application.history.select_related("actor")


# --- Bookings ---------------------------------------------------------------


def _lock_booking(booking_id):
    opportunity_id = (
        Booking.objects.filter(id=booking_id).values_list("opportunity_id", flat=True).first()
    )
    if opportunity_id is None:
        raise NotFound("Booking not found.")
    opp = _lock_opportunity(opportunity_id)
    return opp, Booking.objects.select_for_update().get(id=booking_id)


@transaction.atomic
def cancel_booking(actor, booking_id, *, reason=""):
    """Either party may cancel a confirmed booking. The application decision stays
    `accepted` (it is history); the seat is released for another performer."""
    opp, booking = _lock_booking(booking_id)
    is_manager = can_manage_opportunity(actor, opp)
    if not (is_manager or booking.performer_id == actor.id):
        raise NotFound("Booking not found.")
    if booking.status == Booking.Status.CANCELLED:
        return booking
    if booking.status != Booking.Status.CONFIRMED:
        raise Conflict("Only confirmed bookings can be cancelled.", code="invalid_transition")
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()
    booking.cancelled_by = actor
    booking.cancellation_reason = reason
    booking.save()
    audit.record(actor=actor, action="booking.cancelled", resource=booking)
    notify_id = booking.performer_id if is_manager and actor.id != booking.performer_id \
        else opp.owner_id
    outbox.publish(
        "booking.cancelled",
        {
            "booking_id": str(booking.id),
            "opportunity_id": str(opp.id),
            "opportunity_title": opp.title,
            "actor_id": str(actor.id),
            "recipient_id": str(notify_id),
        },
    )
    return booking


@transaction.atomic
def record_booking_outcome(actor, booking_id, outcome):
    opp, booking = _lock_booking(booking_id)
    if not can_manage_opportunity(actor, opp):
        if booking.performer_id == actor.id:
            raise Forbidden("Only the organizer records performance outcomes.")
        raise NotFound("Booking not found.")
    if booking.status == outcome:
        return booking
    if booking.status != Booking.Status.CONFIRMED:
        raise Conflict("Only confirmed bookings can be completed.", code="invalid_transition")
    booking.status = outcome
    booking.completed_at = timezone.now() if outcome == Booking.Status.COMPLETED else None
    booking.save()
    audit.record(actor=actor, action=f"booking.{outcome}", resource=booking)
    outbox.publish(
        "booking.outcome_recorded",
        {
            "booking_id": str(booking.id),
            "opportunity_id": str(opp.id),
            "opportunity_title": opp.title,
            "performer_id": str(booking.performer_id),
            "actor_id": str(actor.id),
            "outcome": outcome,
        },
    )
    return booking


def my_bookings(user):
    return Booking.objects.filter(performer=user).select_related(
        "opportunity", "opportunity__event", "performer", "performer__profile"
    )


def opportunity_bookings(viewer, opportunity_id):
    opp = get_visible_opportunity(viewer, opportunity_id)
    if not can_manage_opportunity(viewer, opp):
        raise Forbidden()
    return opp.bookings.select_related("performer", "performer__profile", "opportunity")

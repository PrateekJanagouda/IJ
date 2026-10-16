"""Profiles domain: profile visibility, editing, portfolio, venues."""

from django.db import transaction
from django.db.models import Q

from apps.audit import services as audit
from apps.identity import services as identity
from apps.identity.models import Role
from apps.trust_safety import services as safety
from shared.errors import Forbidden, NotFound, ValidationFailed

from .models import (
    ArtistDetails,
    Genre,
    OrganizerDetails,
    PortfolioItem,
    Profile,
    Skill,
    Venue,
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


@transaction.atomic
def create_venue(actor, data):
    if not identity.has_role(actor, Role.ORGANIZER):
        raise Forbidden("Only organizers can create venues.", code="role_required")
    venue = Venue.objects.create(created_by=actor, **data)
    VenueMembership.objects.create(venue=venue, user=actor)
    audit.record(actor=actor, action="venue.created", resource=venue)
    return venue


@transaction.atomic
def update_venue(actor, venue, data):
    if not is_venue_manager(actor, venue.id):
        raise Forbidden()
    for field, value in data.items():
        setattr(venue, field, value)
    venue.save()
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

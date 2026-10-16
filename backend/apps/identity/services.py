"""Identity domain services: accounts, roles, account status."""

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.audit import services as audit
from shared.errors import Conflict, Forbidden, NotFound, ValidationFailed

from .models import SELF_SERVICE_ROLES, AccountStatus, Role, RoleAssignment, User, normalize_email


def roles_of(user):
    if not user or not user.is_authenticated:
        return set()
    cached = getattr(user, "_role_cache", None)
    if cached is None:
        cached = set(RoleAssignment.objects.filter(user=user).values_list("role", flat=True))
        user._role_cache = cached
    return cached


def has_role(user, role):
    return role in roles_of(user)


def is_moderator(user):
    return bool(roles_of(user) & {Role.MODERATOR, Role.ADMINISTRATOR})


def is_administrator(user):
    return has_role(user, Role.ADMINISTRATOR)


def validate_new_password(password, user=None):
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationFailed(details={"fields": {"password": list(exc.messages)}}) from exc


@transaction.atomic
def register_user(*, email, password, display_name, roles=()):
    from apps.profiles import services as profile_services

    email = normalize_email(email)
    roles = set(roles)
    if not roles <= SELF_SERVICE_ROLES:
        raise ValidationFailed(details={"fields": {"roles": ["Only artist or organizer."]}})
    candidate = User(email=email, display_name=display_name)
    validate_new_password(password, candidate)
    if User.objects.filter(email=email).exists():
        # Registration inherently reveals existence; rate limiting reduces enumeration.
        raise Conflict("An account with this email already exists.", code="email_taken")
    try:
        user = User.objects.create_user(email=email, password=password, display_name=display_name)
    except IntegrityError as exc:
        raise Conflict("An account with this email already exists.", code="email_taken") from exc
    RoleAssignment.objects.bulk_create([RoleAssignment(user=user, role=r) for r in roles])
    profile_services.create_profile_for_user(user)
    audit.record(actor=user, action="account.registered", resource=user)
    return user


@transaction.atomic
def grant_role(*, actor, user, role):
    if role not in Role.values:
        raise ValidationFailed(details={"fields": {"role": ["Unknown role."]}})
    if role in SELF_SERVICE_ROLES:
        if actor.id != user.id and not is_administrator(actor):
            raise Forbidden()
    elif not is_administrator(actor):
        raise Forbidden("Only administrators can grant this role.")
    _, created = RoleAssignment.objects.get_or_create(user=user, role=role)
    if created:
        audit.record(actor=actor, action="role.granted", resource=user, metadata={"role": role})
        user.__dict__.pop("_role_cache", None)
    return created


@transaction.atomic
def revoke_role(*, actor, user, role):
    if not is_administrator(actor) and not (actor.id == user.id and role in SELF_SERVICE_ROLES):
        raise Forbidden()
    deleted, _ = RoleAssignment.objects.filter(user=user, role=role).delete()
    if deleted:
        audit.record(actor=actor, action="role.revoked", resource=user, metadata={"role": role})


def get_active_user(user_id):
    user = User.objects.filter(id=user_id, is_active=True).first()
    if user is None:
        raise NotFound("User not found.")
    return user


@transaction.atomic
def set_account_status(*, actor, user, status, reason_code=""):
    """Used by trust & safety. Suspension disables login and invalidates existing sessions
    because session authentication rejects inactive users on every request."""
    if status not in AccountStatus.values:
        raise ValidationFailed()
    if user.id == actor.id:
        raise Conflict("You cannot change your own account status.", code="self_moderation")
    user.account_status = status
    user.is_active = status == AccountStatus.ACTIVE
    user.save(update_fields=["account_status", "is_active", "updated_at"])
    audit.record(
        actor=actor,
        action="account.status_changed",
        resource=user,
        metadata={"status": status, "reason_code": reason_code},
    )
    return user

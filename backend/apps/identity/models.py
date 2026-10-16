import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


def normalize_email(email):
    return (email or "").strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("display_name", "Administrator")
        user = self.create_user(email, password, **extra)
        RoleAssignment.objects.get_or_create(user=user, role=Role.ADMINISTRATOR)
        return user


class AccountStatus(models.TextChoices):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETION_PENDING = "deletion_pending"


class User(AbstractBaseUser, PermissionsMixin):
    """Canonical account. One account may hold several roles (artist + organizer)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)  # always stored normalized (lowercase)
    display_name = models.CharField(max_length=80)
    account_status = models.CharField(
        max_length=20, choices=AccountStatus.choices, default=AccountStatus.ACTIVE
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access only
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.display_name or self.email


class Role(models.TextChoices):
    ARTIST = "artist"
    ORGANIZER = "organizer"
    MODERATOR = "moderator"
    ADMINISTRATOR = "administrator"


SELF_SERVICE_ROLES = {Role.ARTIST, Role.ORGANIZER}


class RoleAssignment(models.Model):
    """Global capability. Never sufficient on its own for access to a specific resource."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_assignments"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role"),
        ]

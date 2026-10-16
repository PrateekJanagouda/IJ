from rest_framework import serializers

from apps.identity import services
from apps.identity.models import SELF_SERVICE_ROLES, User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, write_only=True)
    display_name = serializers.CharField(max_length=80)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=sorted(SELF_SERVICE_ROLES)), required=False,
        default=list, max_length=2,
    )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, write_only=True)


class MeSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    profile_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "account_status", "roles", "profile_id",
                  "created_at"]
        read_only_fields = ["id", "email", "account_status", "roles", "profile_id", "created_at"]

    def get_roles(self, user) -> list[str]:
        return sorted(services.roles_of(user))

    def get_profile_id(self, user) -> str | None:
        profile = getattr(user, "profile", None)
        return str(profile.id) if profile else None


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=sorted(SELF_SERVICE_ROLES))


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128)
    new_password = serializers.CharField(max_length=128)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(max_length=128)

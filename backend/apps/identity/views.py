from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.audit import services as audit
from shared.auth import enforce_csrf
from shared.errors import DomainError, ValidationFailed

from . import services
from .models import User, normalize_email
from .serializers import (
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    RoleSerializer,
)


class InvalidCredentials(DomainError):
    status_code = 401
    code = "invalid_credentials"
    message = "Email or password is incorrect."


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(GenericAPIView):
    """Sets the csrftoken cookie so the SPA can send X-CSRFToken on writes."""

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None})
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_scope = "auth"

    def post(self, request):
        enforce_csrf(request)
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.register_user(**data.validated_data)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = "auth"

    def post(self, request):
        enforce_csrf(request)
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=normalize_email(data.validated_data["email"]),
            password=data.validated_data["password"],
        )
        if user is None:
            audit.record(actor=None, action="auth.login_failed", outcome="failure")
            raise InvalidCredentials()
        login(request, user)  # rotates the session key (prevents session fixation)
        audit.record(actor=user, action="auth.login", resource=user)
        return Response(MeSerializer(user).data)


class LogoutView(GenericAPIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)  # flushes the server-side session
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(GenericAPIView):
    serializer_class = MeSerializer

    def get(self, request):
        return Response(self.get_serializer(request.user).data)

    def patch(self, request):
        data = self.get_serializer(request.user, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        return Response(data.data)


class MyRolesView(GenericAPIView):
    serializer_class = RoleSerializer

    def post(self, request):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.grant_role(actor=request.user, user=request.user, role=data.validated_data["role"])
        return Response(MeSerializer(request.user).data, status=status.HTTP_201_CREATED)


class PasswordChangeView(GenericAPIView):
    serializer_class = PasswordChangeSerializer
    throttle_scope = "auth"

    def post(self, request):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(data.validated_data["current_password"]):
            raise ValidationFailed(details={"fields": {"current_password": ["Incorrect."]}})
        services.validate_new_password(data.validated_data["new_password"], user)
        user.set_password(data.validated_data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)  # keep this session, invalidate others
        audit.record(actor=user, action="auth.password_changed", resource=user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_scope = "password_reset"

    def post(self, request):
        enforce_csrf(request)
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(
            email=normalize_email(data.validated_data["email"]), is_active=True
        ).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}"
            send_mail(
                "Reset your EQora password",
                f"Use this link to reset your password (valid for 1 hour):\n{link}\n\n"
                "If you did not request this, you can ignore this email.",
                None,
                [user.email],
            )
            audit.record(actor=None, action="auth.password_reset_requested", resource=user)
        # Same response either way so the endpoint cannot be used to enumerate accounts.
        return Response(
            {"detail": "If an account exists for that email, a reset link has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_scope = "password_reset"

    def post(self, request):
        enforce_csrf(request)
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            pk = force_str(urlsafe_base64_decode(data.validated_data["uid"]))
            user = User.objects.get(pk=pk, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist, DjangoValidationError):
            user = None
        if user is None or not default_token_generator.check_token(
            user, data.validated_data["token"]
        ):
            raise ValidationFailed("This reset link is invalid or has expired.",
                                   code="invalid_reset_token")
        services.validate_new_password(data.validated_data["new_password"], user)
        user.set_password(data.validated_data["new_password"])
        user.save(update_fields=["password"])  # changes the hash -> old sessions invalid
        audit.record(actor=user, action="auth.password_reset_completed", resource=user)
        return Response(status=status.HTTP_204_NO_CONTENT)

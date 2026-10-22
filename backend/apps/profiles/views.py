from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.identity import services as identity
from shared.pagination import OldestFirstCursorPagination
from shared.throttling import WriteScopedThrottleMixin

from . import services
from .models import Genre, Skill, Venue, VenueBooking
from .serializers import (
    AvailabilitySerializer,
    GenreSerializer,
    PortfolioItemSerializer,
    ProfileListSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    SkillSerializer,
    VenueBlockInputSerializer,
    VenueBookingInputSerializer,
    VenueBookingSerializer,
    VenueManagerSerializer,
    VenueSerializer,
)


class GenreListView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = GenreSerializer
    pagination_class = None

    def get(self, request):
        return Response(self.get_serializer(Genre.objects.all(), many=True).data)


class SkillListView(GenreListView):
    serializer_class = SkillSerializer

    def get(self, request):
        return Response(self.get_serializer(Skill.objects.all(), many=True).data)


class ProfileSearchView(ListModelMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProfileListSerializer

    def get(self, request):
        p = request.query_params
        qs = services.search_profiles(
            request.user, q=p.get("q"), genre=p.get("genre"), skill=p.get("skill"),
            location=p.get("location"), role=p.get("role"),
        ).prefetch_related("artist__genres", "artist__skills")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class ProfileDetailView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProfileSerializer

    def get(self, request, profile_id):
        profile = services.get_visible_profile(request.user, profile_id)
        return Response(self.get_serializer(profile).data)


class MyProfileView(GenericAPIView):
    serializer_class = ProfileSerializer

    def get(self, request):
        return Response(self.get_serializer(services.get_own_profile(request.user)).data)

    def patch(self, request):
        data = ProfileUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        artist, organizer = values.pop("artist", None), values.pop("organizer", None)
        profile = services.update_own_profile(
            request.user, core=values, artist=artist, organizer=organizer
        )
        return Response(self.get_serializer(profile).data)


class MyPortfolioView(GenericAPIView):
    serializer_class = PortfolioItemSerializer
    pagination_class = None

    def get(self, request):
        profile = services.get_own_profile(request.user)
        return Response(self.get_serializer(profile.portfolio.all(), many=True).data)

    def post(self, request):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = services.add_portfolio_item(request.user, data.validated_data)
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)


class MyPortfolioItemView(GenericAPIView):
    serializer_class = PortfolioItemSerializer

    def patch(self, request, item_id):
        item = services.get_own_portfolio_item(request.user, item_id)
        data = self.get_serializer(item, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        return Response(data.data)

    def delete(self, request, item_id):
        services.get_own_portfolio_item(request.user, item_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VenueListView(ListModelMixin, GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = VenueSerializer
    pagination_class = OldestFirstCursorPagination

    def get(self, request):
        """Listed venues. `?managed=true` returns the caller's own, listed or not."""
        if request.query_params.get("managed") == "true" and request.user.is_authenticated:
            qs = Venue.objects.filter(id__in=services.managed_venue_ids(request.user))
            qs = qs.prefetch_related("photos", "memberships__user__profile")
        else:
            qs = services.listed_venues()
        if city := request.query_params.get("city"):
            qs = qs.filter(city__icontains=city)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def post(self, request):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        venue = services.create_venue(request.user, data.validated_data)
        return Response(self.get_serializer(venue).data, status=status.HTTP_201_CREATED)


class VenueDetailView(GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = VenueSerializer

    def get(self, request, venue_id):
        return Response(self.get_serializer(services.get_venue(venue_id)).data)

    def patch(self, request, venue_id):
        venue = services.get_venue(venue_id)
        data = self.get_serializer(venue, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        venue = services.update_venue(request.user, venue, data.validated_data)
        return Response(self.get_serializer(venue).data)


class VenueManagersView(GenericAPIView):
    serializer_class = VenueManagerSerializer

    def post(self, request, venue_id):
        venue = services.get_venue(venue_id)
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = identity.get_active_user(data.validated_data["user_id"])
        services.add_venue_manager(request.user, venue, user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VenueAvailabilityView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AvailabilitySerializer

    @extend_schema(parameters=[
        OpenApiParameter("start", OpenApiTypes.DATE, description="First day (default today)"),
        OpenApiParameter("days", OpenApiTypes.INT, description="Window length, 1-92 (default 42)"),
    ])
    def get(self, request, venue_id):
        venue = services.get_venue(venue_id)
        start = request.query_params.get("start")
        start = (serializers.DateField().run_validation(start) if start
                 else timezone.localtime(timezone.now(), services.VENUE_TZ).date())
        days = serializers.IntegerField(min_value=1, max_value=92).run_validation(
            request.query_params.get("days", 42))
        result = services.availability(request.user, venue, start, days)
        return Response(self.get_serializer(result).data)


class VenueBookingsView(WriteScopedThrottleMixin, GenericAPIView):
    """GET: the venue's bookings and requests (managers only). POST: request a date."""

    serializer_class = VenueBookingSerializer
    pagination_class = None
    throttle_scope = "venue_bookings"

    def get(self, request, venue_id):
        venue = services.get_venue(venue_id)
        qs = services.venue_bookings_for_manager(request.user, venue)
        return Response(self.get_serializer(qs, many=True).data)

    @extend_schema(request=VenueBookingInputSerializer, responses={201: VenueBookingSerializer})
    def post(self, request, venue_id):
        venue = services.get_venue(venue_id)
        data = VenueBookingInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        booking = services.request_booking(request.user, venue, **data.validated_data)
        return Response(self.get_serializer(booking).data, status=status.HTTP_201_CREATED)


class VenueBlockView(GenericAPIView):
    serializer_class = VenueBookingSerializer

    @extend_schema(request=VenueBlockInputSerializer, responses={201: VenueBookingSerializer})
    def post(self, request, venue_id):
        venue = services.get_venue(venue_id)
        data = VenueBlockInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        booking = services.block_slot(request.user, venue, **data.validated_data)
        return Response(self.get_serializer(booking).data, status=status.HTTP_201_CREATED)


class VenueBookingActionView(GenericAPIView):
    serializer_class = VenueBookingSerializer
    action = None

    @extend_schema(request=None)
    def post(self, request, booking_id):
        if self.action == "cancel":
            booking = services.cancel_booking(request.user, booking_id)
        else:
            to = {"confirm": VenueBooking.Status.CONFIRMED,
                  "decline": VenueBooking.Status.DECLINED}[self.action]
            booking = services.decide_booking(request.user, booking_id, to)
        return Response(self.get_serializer(booking).data)


class MyVenueBookingsView(GenericAPIView):
    serializer_class = VenueBookingSerializer
    pagination_class = None

    def get(self, request):
        qs = services.my_venue_bookings(request.user)
        return Response(self.get_serializer(qs, many=True).data)

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.identity import services as identity
from shared.pagination import OldestFirstCursorPagination

from . import services
from .models import Genre, Skill, Venue
from .serializers import (
    GenreSerializer,
    PortfolioItemSerializer,
    ProfileListSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    SkillSerializer,
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
        qs = Venue.objects.all()
        if city := request.query_params.get("city"):
            qs = qs.filter(city__icontains=city)
        if request.query_params.get("managed") == "true" and request.user.is_authenticated:
            qs = qs.filter(id__in=services.managed_venue_ids(request.user))
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

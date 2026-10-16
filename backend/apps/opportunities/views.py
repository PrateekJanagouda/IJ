from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.identity import services as identity
from shared.errors import Forbidden
from shared.pagination import OldestFirstCursorPagination
from shared.serializers import ConfirmReasonSerializer, ReasonSerializer, UserSummarySerializer
from shared.throttling import WriteScopedThrottleMixin

from . import metrics, services
from .models import Application, Booking
from .serializers import (
    ApplicationInputSerializer,
    ApplicationSerializer,
    BookingSerializer,
    DiscoveryQuerySerializer,
    EventInputSerializer,
    EventQuerySerializer,
    EventSerializer,
    OpportunityDetailSerializer,
    OpportunityInputSerializer,
    OpportunitySerializer,
    StatusChangeSerializer,
)


def _paginated(view, qs, serializer_class):
    page = view.paginate_queryset(qs)
    data = serializer_class(page, many=True, context=view.get_serializer_context()).data
    return view.get_paginated_response(data)


# --- Events -----------------------------------------------------------------


class EventListView(WriteScopedThrottleMixin, ListModelMixin, GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = EventSerializer
    throttle_scope = "listings"


    def get(self, request):
        q = EventQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        qs = services.discover_events(request.user, **q.validated_data)
        return _paginated(self, qs, EventSerializer)

    def post(self, request):
        data = EventInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        event = services.create_event(request.user, dict(data.validated_data))
        return Response(self.get_serializer(event).data, status=status.HTTP_201_CREATED)


class ManagedEventListView(ListModelMixin, GenericAPIView):
    serializer_class = EventSerializer

    def get(self, request):
        return _paginated(self, services.managed_events(request.user), EventSerializer)


class EventDetailView(GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = EventSerializer

    def get(self, request, event_id):
        event = services.get_visible_event(request.user, event_id)
        return Response(self.get_serializer(event).data)

    def patch(self, request, event_id):
        data = EventInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        event = services.update_event(request.user, event_id, dict(data.validated_data))
        return Response(self.get_serializer(event).data)


class EventPublishView(GenericAPIView):
    serializer_class = EventSerializer

    def post(self, request, event_id):
        event = services.publish_event(request.user, event_id)
        return Response(self.get_serializer(event).data)


class EventCompleteView(EventPublishView):
    def post(self, request, event_id):
        event = services.complete_event(request.user, event_id)
        return Response(self.get_serializer(event).data)


class EventCancelView(GenericAPIView):
    serializer_class = ConfirmReasonSerializer

    def post(self, request, event_id):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        event = services.cancel_event(request.user, event_id, **data.validated_data)
        # Child opportunities still needing a manual decision (no automatic cascade).
        unresolved = services.event_opportunities(request.user, event).filter(
            status__in=["draft", "published", "closed"]
        )
        ctx = self.get_serializer_context()
        return Response({
            "event": EventSerializer(event, context=ctx).data,
            "opportunities_awaiting_review": OpportunitySerializer(
                unresolved, many=True, context=ctx
            ).data,
        })


class EventOpportunitiesView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = OpportunitySerializer
    pagination_class = None

    def get(self, request, event_id):
        event = services.get_visible_event(request.user, event_id)
        qs = services.event_opportunities(request.user, event).prefetch_related("genres", "skills")
        return Response(self.get_serializer(qs, many=True).data)


class EventLineupView(GenericAPIView):
    serializer_class = BookingSerializer
    pagination_class = None

    def get(self, request, event_id):
        event = services.get_visible_event(request.user, event_id)
        lineup = services.event_lineup(request.user, event)
        return Response(self.get_serializer(lineup, many=True).data)


# --- Opportunities ----------------------------------------------------------


class OpportunityListView(WriteScopedThrottleMixin, ListModelMixin, GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = OpportunitySerializer
    throttle_scope = "listings"


    def get(self, request):
        q = DiscoveryQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        v = q.validated_data
        qs = services.discover_opportunities(
            request.user, q=v.get("q"), opportunity_type=v.get("type"),
            compensation_type=v.get("compensation"), genre=v.get("genre"),
            skill=v.get("skill"), location=v.get("location"),
            starts_after=v.get("starts_after"), starts_before=v.get("starts_before"),
            event_id=v.get("event"), include_closed=v["include_closed"],
        )
        return _paginated(self, qs, OpportunitySerializer)

    def post(self, request):
        data = OpportunityInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        opp = services.create_opportunity(request.user, dict(data.validated_data))
        ctx = self.get_serializer_context()
        return Response(OpportunityDetailSerializer(opp, context=ctx).data,
                        status=status.HTTP_201_CREATED)


class ManagedOpportunityListView(ListModelMixin, GenericAPIView):
    serializer_class = OpportunitySerializer

    def get(self, request):
        qs = services.managed_opportunities(request.user)
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s)
        return _paginated(self, qs, OpportunitySerializer)


class OpportunityDetailView(GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = OpportunityDetailSerializer

    def get(self, request, opportunity_id):
        opp = services.get_visible_opportunity(request.user, opportunity_id)
        return Response(self.get_serializer(opp).data)

    def patch(self, request, opportunity_id):
        data = OpportunityInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        values.pop("event", None)  # an opportunity cannot be moved between events
        opp = services.update_opportunity(request.user, opportunity_id, values)
        return Response(self.get_serializer(opp).data)


def _opportunity_action(fn):
    class View(GenericAPIView):
        serializer_class = OpportunityDetailSerializer

        def post(self, request, opportunity_id):
            opp = fn(request.user, opportunity_id)
            return Response(self.get_serializer(opp).data)

    return View


OpportunityPublishView = _opportunity_action(services.publish_opportunity)
OpportunityCloseView = _opportunity_action(services.close_opportunity)
OpportunityCompleteView = _opportunity_action(services.complete_opportunity)


class OpportunityCancelView(GenericAPIView):
    serializer_class = ConfirmReasonSerializer

    def post(self, request, opportunity_id):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        opp = services.cancel_opportunity(request.user, opportunity_id, **data.validated_data)
        ctx = self.get_serializer_context()
        return Response(OpportunityDetailSerializer(opp, context=ctx).data)


class OpportunityApplicationsView(WriteScopedThrottleMixin, ListModelMixin, GenericAPIView):
    """GET: managers review applicants. POST: an artist applies."""

    serializer_class = ApplicationSerializer
    pagination_class = OldestFirstCursorPagination
    throttle_scope = "applications"


    def get(self, request, opportunity_id):
        qs = services.applications_for_opportunity(
            request.user, opportunity_id, status=request.query_params.get("status")
        )
        return _paginated(self, qs, ApplicationSerializer)

    def post(self, request, opportunity_id):
        data = ApplicationInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        application = services.submit_application(
            request.user, opportunity_id, **data.validated_data
        )
        return Response(self.get_serializer(application).data, status=status.HTTP_201_CREATED)


class OpportunityBookingsView(GenericAPIView):
    serializer_class = BookingSerializer
    pagination_class = None

    def get(self, request, opportunity_id):
        qs = services.opportunity_bookings(request.user, opportunity_id)
        return Response(self.get_serializer(qs, many=True).data)


# --- Applications -----------------------------------------------------------


class MyApplicationsView(ListModelMixin, GenericAPIView):
    serializer_class = ApplicationSerializer

    def get(self, request):
        qs = services.my_applications(request.user, status=request.query_params.get("status"))
        return _paginated(self, qs.select_related("booking"), ApplicationSerializer)


class ApplicationDetailView(GenericAPIView):
    serializer_class = ApplicationSerializer

    def get(self, request, application_id):
        return Response(self.get_serializer(
            services.get_application(request.user, application_id)
        ).data)


class ApplicationHistoryView(GenericAPIView):
    serializer_class = StatusChangeSerializer
    pagination_class = None

    def get(self, request, application_id):
        qs = services.application_history(request.user, application_id)
        return Response(self.get_serializer(qs, many=True).data)


def _application_action(to_status):
    class View(GenericAPIView):
        serializer_class = ReasonSerializer

        def post(self, request, application_id):
            data = self.get_serializer(data=request.data)
            data.is_valid(raise_exception=True)
            services.transition_application(
                request.user, application_id, to_status, reason=data.validated_data["reason"]
            )
            application = services.get_application(request.user, application_id)
            return Response(ApplicationSerializer(
                application, context=self.get_serializer_context()
            ).data)

    View.__name__ = f"Application{to_status.title()}View"
    return View


ApplicationShortlistView = _application_action(Application.Status.SHORTLISTED)
ApplicationAcceptView = _application_action(Application.Status.ACCEPTED)
ApplicationDeclineView = _application_action(Application.Status.DECLINED)
ApplicationWithdrawView = _application_action(Application.Status.WITHDRAWN)


# --- Bookings ---------------------------------------------------------------


class MyBookingsView(ListModelMixin, GenericAPIView):
    serializer_class = BookingSerializer

    def get(self, request):
        return _paginated(self, services.my_bookings(request.user), BookingSerializer)


class BookingCancelView(GenericAPIView):
    serializer_class = ReasonSerializer

    def post(self, request, booking_id):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        booking = services.cancel_booking(request.user, booking_id, **data.validated_data)
        return Response(BookingSerializer(booking).data)


def _booking_outcome(outcome):
    class View(GenericAPIView):
        serializer_class = BookingSerializer

        def post(self, request, booking_id):
            booking = services.record_booking_outcome(request.user, booking_id, outcome)
            return Response(self.get_serializer(booking).data)

    return View


BookingCompleteView = _booking_outcome(Booking.Status.COMPLETED)
BookingNoShowView = _booking_outcome(Booking.Status.NO_SHOW)


class FunnelMetricsView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSummarySerializer  # schema placeholder; response is a plain list

    def get(self, request):
        if not identity.is_administrator(request.user):
            raise Forbidden()
        return Response({"months": metrics.funnel_by_month()})

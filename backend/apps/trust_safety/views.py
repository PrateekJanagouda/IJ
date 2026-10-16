from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response

from apps.identity import services as identity
from shared.throttling import WriteScopedThrottleMixin

from . import services
from .models import UserBlock
from .serializers import (
    BlockInputSerializer,
    BlockSerializer,
    ModerationActionInputSerializer,
    ModerationActionSerializer,
    ModeratorReportSerializer,
    MyReportSerializer,
    ReportInputSerializer,
)


class ReportListView(WriteScopedThrottleMixin, ListModelMixin, GenericAPIView):
    """Users file reports and see their own. Reporter identity is never exposed to the
    reported party."""

    serializer_class = MyReportSerializer
    throttle_scope = "reports"


    def get(self, request):
        page = self.paginate_queryset(services.Report.objects.filter(reporter=request.user))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def post(self, request):
        data = ReportInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        report, created = services.submit_report(request.user, **data.validated_data)
        return Response(self.get_serializer(report).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BlockListView(ListModelMixin, GenericAPIView):
    serializer_class = BlockSerializer

    def get(self, request):
        qs = UserBlock.objects.filter(blocker=request.user).select_related(
            "blocked", "blocked__profile"
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def post(self, request):
        data = BlockInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        target = identity.get_active_user(data.validated_data["user_id"])
        created = services.block_user(request.user, target)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BlockDetailView(GenericAPIView):
    @extend_schema(request=None, responses={204: None})
    def delete(self, request, user_id):
        services.unblock_user(request.user, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModerationQueueView(ListModelMixin, GenericAPIView):
    serializer_class = ModeratorReportSerializer

    def get(self, request):
        qs = services.moderation_queue(request.user, request.query_params.get("status"))
        page = self.paginate_queryset(qs.prefetch_related("actions__moderator"))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class ModerationReportView(GenericAPIView):
    serializer_class = ModeratorReportSerializer

    def get(self, request, report_id):
        report = services.get_report_for_moderator(request.user, report_id)
        body = self.get_serializer(report).data
        body["target"] = services.target_preview(request.user, report)
        return Response(body)


class ModerationActionView(GenericAPIView):
    serializer_class = ModerationActionSerializer

    def post(self, request, report_id):
        report = services.get_report_for_moderator(request.user, report_id)
        data = ModerationActionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        action = services.take_action(request.user, report, **data.validated_data)
        return Response(self.get_serializer(action).data, status=status.HTTP_201_CREATED)

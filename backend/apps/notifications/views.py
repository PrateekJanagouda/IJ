from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response

from shared.serializers import UnreadCountSerializer

from . import services
from .serializers import NotificationSerializer


class NotificationListView(ListModelMixin, GenericAPIView):
    serializer_class = NotificationSerializer

    def get(self, request):
        qs = services.for_user(request.user,
                               unread_only=request.query_params.get("unread") == "true")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class UnreadCountView(GenericAPIView):
    @extend_schema(responses=UnreadCountSerializer)
    def get(self, request):
        return Response({"unread": services.unread_count(request.user)})


class MarkReadView(GenericAPIView):
    serializer_class = NotificationSerializer

    def post(self, request, notification_id):
        return Response(self.get_serializer(
            services.mark_read(request.user, notification_id)
        ).data)


class MarkAllReadView(GenericAPIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        services.mark_all_read(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

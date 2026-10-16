from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from apps.notifications import services as notifications
from shared.serializers import UnreadCountSerializer
from shared.throttling import WriteScopedThrottleMixin

from . import services
from .serializers import (
    ArchiveSerializer,
    ConversationSerializer,
    MessageSerializer,
    SendMessageSerializer,
    StartConversationSerializer,
)


class InboxPagination(LimitOffsetPagination):
    default_limit = 30
    max_limit = 100


class ConversationListView(WriteScopedThrottleMixin, ListModelMixin, GenericAPIView):
    serializer_class = ConversationSerializer
    pagination_class = InboxPagination
    throttle_scope = "conversations"


    def get(self, request):
        archived = request.query_params.get("archived") == "true"
        qs = services.conversations_for(request.user, archived=archived)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def post(self, request):
        data = StartConversationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        conversation, created = services.start_direct_conversation(
            request.user, data.validated_data["user_id"]
        )
        body = self.get_serializer(services.get_conversation(request.user, conversation.id)).data
        return Response(body, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConversationDetailView(GenericAPIView):
    serializer_class = ConversationSerializer

    def get(self, request, conversation_id):
        return Response(self.get_serializer(
            services.get_conversation(request.user, conversation_id)
        ).data)


class ConversationMessagesView(WriteScopedThrottleMixin, ListModelMixin, GenericAPIView):
    serializer_class = MessageSerializer
    throttle_scope = "messages"


    def get(self, request, conversation_id):
        qs = services.messages_for(request.user, conversation_id)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def post(self, request, conversation_id):
        data = SendMessageSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        message = services.send_message(request.user, conversation_id, **data.validated_data)
        return Response(self.get_serializer(message).data, status=status.HTTP_201_CREATED)


class ConversationReadView(GenericAPIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request, conversation_id):
        services.mark_read(request.user, conversation_id)
        notifications.mark_conversation_read(request.user, conversation_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationArchiveView(GenericAPIView):
    serializer_class = ArchiveSerializer

    def post(self, request, conversation_id):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_archived(request.user, conversation_id, data.validated_data["archived"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageDetailView(GenericAPIView):
    @extend_schema(request=None, responses={204: None})
    def delete(self, request, message_id):
        services.delete_message(request.user, message_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnreadMessagesView(GenericAPIView):
    @extend_schema(responses=UnreadCountSerializer)
    def get(self, request):
        return Response({"unread": services.total_unread(request.user)})

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from shared.pagination import OldestFirstCursorPagination
from shared.throttling import WriteScopedThrottleMixin

from . import services
from .serializers import (
    CommentInputSerializer,
    CommentSerializer,
    FollowSerializer,
    PostInputSerializer,
    PostSerializer,
    RepostInputSerializer,
)


def _page(view, qs, serializer_class, **context):
    page = view.paginate_queryset(qs)
    ctx = {**view.get_serializer_context(), **context}
    return view.get_paginated_response(serializer_class(page, many=True, context=ctx).data)


class WriteThrottledView(WriteScopedThrottleMixin, GenericAPIView):
    """Base for social endpoints whose writes carry a per-feature rate limit."""


class HomeFeedView(ListModelMixin, GenericAPIView):
    serializer_class = PostSerializer

    def get(self, request):
        return _page(self, services.home_feed(request.user), PostSerializer)


class DiscoverFeedView(ListModelMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PostSerializer

    def get(self, request):
        return _page(self, services.discover_feed(request.user), PostSerializer)


class PostListView(ListModelMixin, WriteThrottledView):
    """GET ?author=<user_id> lists a user's posts. POST creates a post."""

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = PostSerializer
    throttle_scope = "posts"

    def get(self, request):
        author = request.query_params.get("author")
        if author:
            author = serializers.UUIDField().run_validation(author)
        qs = services.posts_by_author(request.user, author) if author else \
            services.discover_feed(request.user)
        return _page(self, qs, PostSerializer)

    def post(self, request):
        data = PostInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        post = services.create_post(request.user, **data.validated_data)
        post = services.get_visible_post(request.user, post.id)
        return Response(self.get_serializer(post).data, status=status.HTTP_201_CREATED)


class PostDetailView(GenericAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = PostSerializer

    def get(self, request, post_id):
        return Response(self.get_serializer(services.get_visible_post(request.user, post_id)).data)

    def patch(self, request, post_id):
        data = PostInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        services.update_post(request.user, post_id, data.validated_data)
        return Response(self.get_serializer(services.get_visible_post(request.user, post_id)).data)

    def delete(self, request, post_id):
        services.delete_post(request.user, post_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RepostView(WriteThrottledView):
    serializer_class = PostSerializer
    throttle_scope = "posts"

    def post(self, request, post_id):
        data = RepostInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        post = services.repost(request.user, post_id, **data.validated_data)
        post = services.get_visible_post(request.user, post.id)
        return Response(self.get_serializer(post).data, status=status.HTTP_201_CREATED)


class PostLikeView(WriteThrottledView):
    throttle_scope = "social"

    @extend_schema(request=None, responses={200: None, 201: None})
    def post(self, request, post_id):
        created = services.like_post(request.user, post_id)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, post_id):
        services.unlike_post(request.user, post_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostCommentsView(ListModelMixin, WriteThrottledView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = CommentSerializer
    pagination_class = OldestFirstCursorPagination
    throttle_scope = "comments"

    def get(self, request, post_id):
        return _page(self, services.visible_comments(request.user, post_id), CommentSerializer)

    def post(self, request, post_id):
        data = CommentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        comment = services.add_comment(request.user, post_id, **data.validated_data)
        return Response(self.get_serializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDetailView(GenericAPIView):
    @extend_schema(request=None, responses={204: None})
    def delete(self, request, comment_id):
        services.delete_comment(request.user, comment_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowView(WriteThrottledView):
    throttle_scope = "social"

    @extend_schema(request=None, responses={200: None, 201: None})
    def post(self, request, user_id):
        created = services.follow(request.user, user_id)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, user_id):
        services.unfollow(request.user, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowersView(ListModelMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = FollowSerializer

    def get(self, request, user_id):
        return _page(self, services.followers_of(request.user, user_id), FollowSerializer,
                     direction="followers")


class FollowingView(FollowersView):
    def get(self, request, user_id):
        return _page(self, services.following_of(request.user, user_id), FollowSerializer,
                     direction="following")

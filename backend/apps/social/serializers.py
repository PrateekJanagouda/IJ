from django.conf import settings
from rest_framework import serializers

from shared.serializers import UserSummarySerializer

from .models import Comment, Post


class EmbeddedPostSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = Post
        fields = ["id", "author", "body", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    repost_of = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    viewer_has_liked = serializers.BooleanField(read_only=True, default=False)
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id", "author", "body", "visibility", "repost_of", "like_count", "comment_count",
            "viewer_has_liked", "share_url", "created_at", "updated_at",
        ]

    def get_repost_of(self, post) -> dict | None:
        original = post.repost_of
        if original is None:
            return None
        # The original may have been deleted/hidden since: show a tombstone, not its body.
        if original.status != Post.Status.PUBLISHED:
            return {"id": str(original.id), "unavailable": True}
        return EmbeddedPostSerializer(original).data

    def get_share_url(self, post) -> str:
        return f"{settings.FRONTEND_BASE_URL}/posts/{post.id}"


class PostInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, allow_blank=True)
    visibility = serializers.ChoiceField(choices=Post.Visibility.choices, required=False)


class RepostInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "post_id", "author", "body", "created_at"]


class CommentInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000)


class FollowSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_user(self, follow) -> dict:
        followers = self.context.get("direction") == "followers"
        target = follow.follower if followers else follow.followed
        return UserSummarySerializer(target).data

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.media import services as media
from shared.serializers import UserSummarySerializer

from .models import Comment, Post


class AttachmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    content_type = serializers.CharField()
    url = serializers.CharField()


def attachments(post):
    return [
        {"id": str(link.media_id), "kind": link.media.kind, "content_type": link.media.content_type,
         "url": media.url_for(link.media_id)}
        for link in post.media_links.all()
    ]


class EmbeddedPostSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    media = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "author", "body", "media", "created_at"]
        read_only_fields = fields

    @extend_schema_field(AttachmentSerializer(many=True))
    def get_media(self, post):
        return attachments(post)


class RepostRefSerializer(serializers.Serializer):
    """The reposted original, or a tombstone ({id, unavailable: true}) if it's gone."""

    id = serializers.UUIDField()
    author = UserSummarySerializer(required=False)
    body = serializers.CharField(required=False)
    created_at = serializers.DateTimeField(required=False)
    media = AttachmentSerializer(many=True, required=False)
    unavailable = serializers.BooleanField(required=False)


class PostSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    repost_of = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    viewer_has_liked = serializers.BooleanField(read_only=True, default=False)
    share_url = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id", "author", "body", "media", "visibility", "repost_of", "like_count",
            "comment_count", "viewer_has_liked", "share_url", "created_at", "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(RepostRefSerializer(allow_null=True))
    def get_repost_of(self, post):
        original = post.repost_of
        if original is None:
            return None
        # The original may have been deleted/hidden since: show a tombstone, not its body.
        if original.status != Post.Status.PUBLISHED:
            return {"id": str(original.id), "unavailable": True}
        return EmbeddedPostSerializer(original).data

    @extend_schema_field(AttachmentSerializer(many=True))
    def get_media(self, post):
        return attachments(post)

    def get_share_url(self, post) -> str:
        return f"{settings.FRONTEND_BASE_URL}/posts/{post.id}"


class PostInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, allow_blank=True, required=False, default="")
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list,
                                      max_length=4)
    visibility = serializers.ChoiceField(choices=Post.Visibility.choices, required=False)


class RepostInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "post_id", "author", "body", "created_at"]
        read_only_fields = fields


class CommentInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000)


class FollowSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    @extend_schema_field(UserSummarySerializer)
    def get_user(self, follow):
        followers = self.context.get("direction") == "followers"
        target = follow.follower if followers else follow.followed
        return UserSummarySerializer(target).data

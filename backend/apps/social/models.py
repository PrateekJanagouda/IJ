from django.conf import settings
from django.db import models
from django.db.models import F, Q

from shared.models import TimeStampedModel


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_set"
    )
    followed = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follower_set"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follows"
        constraints = [
            models.UniqueConstraint(fields=["follower", "followed"], name="uniq_follow"),
            models.CheckConstraint(condition=~Q(follower=F("followed")), name="no_self_follow"),
        ]
        indexes = [
            models.Index(fields=["follower", "-created_at"]),
            models.Index(fields=["followed", "-created_at"]),
        ]


class Post(TimeStampedModel):
    """A post or an internal repost. A repost is a post with `repost_of` set (optionally
    with commentary), so the feed is a single query over one table."""

    class Visibility(models.TextChoices):
        PUBLIC = "public"
        FOLLOWERS = "followers"

    class Status(models.TextChoices):
        PUBLISHED = "published"
        HIDDEN = "hidden"  # by moderation
        DELETED = "deleted"  # by author (soft delete keeps moderation evidence)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="posts"
    )
    body = models.TextField(max_length=5000, blank=True)
    repost_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reposts"
    )
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PUBLISHED)
    # Denormalised so the "not empty" rule stays a database constraint: a check
    # constraint can't look into the attachments table.
    has_media = models.BooleanField(default=False)

    class Meta:
        db_table = "posts"
        constraints = [
            models.CheckConstraint(
                condition=~Q(body="") | Q(repost_of__isnull=False) | Q(has_media=True),
                name="post_has_content",
            ),
            models.UniqueConstraint(
                fields=["author", "repost_of"],
                condition=Q(repost_of__isnull=False, status="published"),
                name="uniq_active_repost",
            ),
        ]
        indexes = [
            models.Index(fields=["author", "-created_at", "-id"]),
            models.Index(fields=["status", "visibility", "-created_at"]),
        ]


class PostMedia(models.Model):
    """Photos and videos attached to a post, in display order."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media_links")
    media = models.ForeignKey("media.MediaAsset", on_delete=models.PROTECT, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "post_media"
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["post", "media"], name="uniq_post_media")]


class Comment(TimeStampedModel):
    class Status(models.TextChoices):
        VISIBLE = "visible"
        HIDDEN = "hidden"
        DELETED = "deleted"

    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comments"
    )
    body = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VISIBLE)

    class Meta:
        db_table = "comments"
        indexes = [models.Index(fields=["post", "created_at", "id"])]


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "post_likes"
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="uniq_post_like")]
        indexes = [models.Index(fields=["user", "-created_at"])]

"""Social domain: follows, posts, reposts, comments, likes and feeds.

Visibility is enforced in the querysets themselves, so every list endpoint, share link,
report lookup and notification resolves through the same rules.
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q

from apps.audit import services as audit
from apps.identity import services as identity
from apps.outbox import services as outbox
from apps.trust_safety import services as safety
from shared.errors import Conflict, Forbidden, NotFound, ValidationFailed

from .models import Comment, Follow, Post, PostLike

# --- Follows ----------------------------------------------------------------


@transaction.atomic
def follow(actor, target_id):
    target = identity.get_active_user(target_id)
    if target.id == actor.id:
        raise ValidationFailed("You cannot follow yourself.", code="self_follow")
    if safety.is_blocked(actor.id, target.id):
        raise NotFound("User not found.")
    try:
        with transaction.atomic():
            Follow.objects.create(follower=actor, followed=target)
    except IntegrityError:
        return False  # already following: idempotent
    outbox.publish("user.followed", {"follower_id": str(actor.id), "followed_id": str(target.id)})
    return True


def unfollow(actor, target_id):
    deleted, _ = Follow.objects.filter(follower=actor, followed_id=target_id).delete()
    return bool(deleted)


def remove_follows_between(user_a, user_b):
    Follow.objects.filter(
        Q(follower=user_a, followed=user_b) | Q(follower=user_b, followed=user_a)
    ).delete()


def followers_of(viewer, user_id):
    identity.get_active_user(user_id)
    qs = Follow.objects.filter(followed_id=user_id, follower__is_active=True).select_related(
        "follower", "follower__profile"
    )
    return safety.exclude_blocked(qs, viewer, "follower")


def following_of(viewer, user_id):
    identity.get_active_user(user_id)
    qs = Follow.objects.filter(follower_id=user_id, followed__is_active=True).select_related(
        "followed", "followed__profile"
    )
    return safety.exclude_blocked(qs, viewer, "followed")


def follow_counts(user_id):
    return {
        "followers": Follow.objects.filter(followed_id=user_id).count(),
        "following": Follow.objects.filter(follower_id=user_id).count(),
    }


def is_following(viewer, user_id):
    if not viewer or not viewer.is_authenticated:
        return False
    return Follow.objects.filter(follower=viewer, followed_id=user_id).exists()


# --- Post visibility --------------------------------------------------------


def visible_posts(viewer):
    """Published posts the viewer may see, annotated for display."""
    qs = Post.objects.filter(status=Post.Status.PUBLISHED, author__is_active=True)
    if viewer is None or not viewer.is_authenticated:
        qs = qs.filter(visibility=Post.Visibility.PUBLIC)
    else:
        follows_author = Follow.objects.filter(follower=viewer, followed=OuterRef("author"))
        qs = qs.filter(
            Q(visibility=Post.Visibility.PUBLIC) | Q(author=viewer) | Exists(follows_author)
        )
        qs = safety.exclude_blocked(qs, viewer, "author")
    return annotate_posts(qs, viewer)


def annotate_posts(qs, viewer):
    qs = qs.select_related("author", "author__profile", "repost_of", "repost_of__author",
                           "repost_of__author__profile")
    qs = qs.annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count(
            "comments", filter=Q(comments__status=Comment.Status.VISIBLE), distinct=True
        ),
    )
    if viewer is not None and viewer.is_authenticated:
        qs = qs.annotate(
            viewer_has_liked=Exists(PostLike.objects.filter(post=OuterRef("pk"), user=viewer))
        )
    return qs


def get_visible_post(viewer, post_id):
    post = visible_posts(viewer).filter(id=post_id).first()
    if post is None:
        raise NotFound("Post not found.")
    return post


def can_view_post(viewer, post):
    return visible_posts(viewer).filter(id=post.id).exists()


def home_feed(viewer):
    """Chronological feed: the viewer's own posts plus posts by accounts they follow."""
    followed = Follow.objects.filter(follower=viewer).values("followed_id")
    return visible_posts(viewer).filter(Q(author=viewer) | Q(author__in=followed))


def discover_feed(viewer):
    return visible_posts(viewer).filter(visibility=Post.Visibility.PUBLIC)


def posts_by_author(viewer, author_id):
    return visible_posts(viewer).filter(author_id=author_id)


# --- Post writes ------------------------------------------------------------


@transaction.atomic
def create_post(actor, *, body, visibility=Post.Visibility.PUBLIC):
    body = (body or "").strip()
    if not body:
        raise ValidationFailed(details={"fields": {"body": ["A post needs text."]}})
    return Post.objects.create(author=actor, body=body, visibility=visibility)


@transaction.atomic
def repost(actor, post_id, *, body=""):
    original = get_visible_post(actor, post_id)
    if original.repost_of_id:
        original = get_visible_post(actor, original.repost_of_id)  # always point at the source
    if original.visibility != Post.Visibility.PUBLIC:
        raise Conflict("Only public posts can be reposted.", code="not_shareable")
    if original.author_id == actor.id:
        raise Conflict("You cannot repost your own post.", code="own_post")
    try:
        with transaction.atomic():
            post = Post.objects.create(
                author=actor, body=(body or "").strip(), repost_of=original,
                visibility=Post.Visibility.PUBLIC,
            )
    except IntegrityError as exc:
        raise Conflict("You have already reposted this.", code="already_reposted") from exc
    outbox.publish(
        "post.reposted",
        {"post_id": str(original.id), "repost_id": str(post.id), "actor_id": str(actor.id),
         "author_id": str(original.author_id)},
    )
    return post


def _own_post_for_update(actor, post_id):
    post = Post.objects.select_for_update().filter(id=post_id).first()
    if post is None or post.status == Post.Status.DELETED:
        raise NotFound("Post not found.")
    if post.author_id != actor.id:
        if can_view_post(actor, post):
            raise Forbidden()
        raise NotFound("Post not found.")
    return post


@transaction.atomic
def update_post(actor, post_id, data):
    post = _own_post_for_update(actor, post_id)
    if post.status == Post.Status.HIDDEN:
        raise Conflict("This post was hidden by moderation.", code="moderated")
    if "body" in data:
        body = (data["body"] or "").strip()
        if not body and not post.repost_of_id:
            raise ValidationFailed(details={"fields": {"body": ["A post needs text."]}})
        post.body = body
    if "visibility" in data:
        if post.repost_of_id and data["visibility"] != Post.Visibility.PUBLIC:
            raise ValidationFailed(details={"fields": {"visibility": ["Reposts are public."]}})
        post.visibility = data["visibility"]
    post.save()
    return post


@transaction.atomic
def delete_post(actor, post_id):
    post = _own_post_for_update(actor, post_id)
    post.status = Post.Status.DELETED
    post.save(update_fields=["status", "updated_at"])


@transaction.atomic
def moderate_post(moderator, post_id, *, hidden):
    post = Post.objects.select_for_update().filter(id=post_id).first()
    if post is None:
        raise NotFound("Post not found.")
    if post.status != Post.Status.DELETED:
        post.status = Post.Status.HIDDEN if hidden else Post.Status.PUBLISHED
        post.save(update_fields=["status", "updated_at"])
    audit.record(actor=moderator, action="moderation.post_" + ("hidden" if hidden else "restored"),
                 resource=post)
    return post


# --- Likes ------------------------------------------------------------------


@transaction.atomic
def like_post(actor, post_id):
    post = get_visible_post(actor, post_id)
    try:
        with transaction.atomic():
            PostLike.objects.create(post_id=post.id, user=actor)
    except IntegrityError:
        return False  # duplicate like: idempotent
    outbox.publish(
        "post.liked",
        {"post_id": str(post.id), "actor_id": str(actor.id), "author_id": str(post.author_id)},
    )
    return True


def unlike_post(actor, post_id):
    deleted, _ = PostLike.objects.filter(post_id=post_id, user=actor).delete()
    return bool(deleted)


# --- Comments ---------------------------------------------------------------


def visible_comments(viewer, post_id):
    post = get_visible_post(viewer, post_id)
    qs = Comment.objects.filter(
        post=post, status=Comment.Status.VISIBLE, author__is_active=True
    ).select_related("author", "author__profile")
    return safety.exclude_blocked(qs, viewer, "author")


def get_visible_comment(viewer, comment_id):
    comment = Comment.objects.filter(id=comment_id, status=Comment.Status.VISIBLE).first()
    if comment is None or not visible_comments(viewer, comment.post_id).filter(
        id=comment.id
    ).exists():
        raise NotFound("Comment not found.")
    return comment


@transaction.atomic
def add_comment(actor, post_id, *, body):
    post = get_visible_post(actor, post_id)
    body = (body or "").strip()
    if not body:
        raise ValidationFailed(details={"fields": {"body": ["A comment needs text."]}})
    comment = Comment.objects.create(post_id=post.id, author=actor, body=body)
    outbox.publish(
        "post.commented",
        {"post_id": str(post.id), "comment_id": str(comment.id), "actor_id": str(actor.id),
         "author_id": str(post.author_id)},
    )
    return comment


@transaction.atomic
def delete_comment(actor, comment_id):
    comment = Comment.objects.select_for_update().filter(id=comment_id).first()
    if comment is None or comment.status == Comment.Status.DELETED:
        raise NotFound("Comment not found.")
    if comment.author_id != actor.id:
        raise Forbidden()
    comment.status = Comment.Status.DELETED
    comment.save(update_fields=["status", "updated_at"])


@transaction.atomic
def moderate_comment(moderator, comment_id, *, hidden):
    comment = Comment.objects.select_for_update().filter(id=comment_id).first()
    if comment is None:
        raise NotFound("Comment not found.")
    if comment.status != Comment.Status.DELETED:
        comment.status = Comment.Status.HIDDEN if hidden else Comment.Status.VISIBLE
        comment.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=moderator, action="moderation.comment_" + ("hidden" if hidden else "restored"),
        resource=comment,
    )
    return comment

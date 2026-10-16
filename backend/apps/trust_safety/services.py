"""Trust & safety: blocks, reports and moderation.

Other domains call `is_blocked` / `exclude_blocked` to enforce blocks at their entry points.
Moderation actions are executed through the owning domain's service, never by writing to
another domain's tables directly.
"""

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.audit import services as audit
from shared.errors import Conflict, Forbidden, NotFound, ValidationFailed

from .models import ModerationAction, Report, TargetType, UserBlock

# --- Blocks -----------------------------------------------------------------


def is_blocked(user_a_id, user_b_id):
    """True if either user has blocked the other."""
    if not user_a_id or not user_b_id or user_a_id == user_b_id:
        return False
    return UserBlock.objects.filter(
        Q(blocker_id=user_a_id, blocked_id=user_b_id)
        | Q(blocker_id=user_b_id, blocked_id=user_a_id)
    ).exists()


def exclude_blocked(queryset, viewer, user_field):
    """Drop rows whose `user_field` is someone the viewer blocked or who blocked the viewer."""
    if viewer is None or not viewer.is_authenticated:
        return queryset
    blocked = UserBlock.objects.filter(blocker=viewer).values("blocked_id")
    blockers = UserBlock.objects.filter(blocked=viewer).values("blocker_id")
    return queryset.exclude(**{f"{user_field}__in": blocked}).exclude(
        **{f"{user_field}__in": blockers}
    )


@transaction.atomic
def block_user(blocker, blocked):
    from apps.social import services as social

    if blocker.id == blocked.id:
        raise ValidationFailed("You cannot block yourself.", code="self_block")
    try:
        with transaction.atomic():
            UserBlock.objects.create(blocker=blocker, blocked=blocked)
    except IntegrityError:
        return False  # already blocked: idempotent
    # Policy (docs/mvp-decisions.md): a block removes follows in both directions. Existing
    # content and message history are kept, but new interactions are refused.
    social.remove_follows_between(blocker, blocked)
    audit.record(actor=blocker, action="user.blocked", resource=blocked)
    return True


@transaction.atomic
def unblock_user(blocker, blocked_id):
    deleted, _ = UserBlock.objects.filter(blocker=blocker, blocked_id=blocked_id).delete()
    if deleted:
        audit.record(actor=blocker, action="user.unblocked", metadata={"user_id": str(blocked_id)})
    return bool(deleted)


# --- Report targets ---------------------------------------------------------


def _resolve_target(viewer, target_type, target_id):
    """Return the target if it exists AND the viewer may see it (raises NotFound otherwise).
    Each domain's own visibility rule is reused, so reporting cannot be used to probe for
    private resources."""
    from apps.identity import services as identity
    from apps.messaging import services as messaging
    from apps.opportunities import services as opportunities
    from apps.social import services as social

    if target_type == TargetType.USER:
        return identity.get_active_user(target_id)
    if target_type == TargetType.POST:
        return social.get_visible_post(viewer, target_id)
    if target_type == TargetType.COMMENT:
        return social.get_visible_comment(viewer, target_id)
    if target_type == TargetType.MESSAGE:
        return messaging.get_message_for_participant(viewer, target_id)
    if target_type == TargetType.OPPORTUNITY:
        return opportunities.get_visible_opportunity(viewer, target_id)
    if target_type == TargetType.EVENT:
        return opportunities.get_visible_event(viewer, target_id)
    raise ValidationFailed(details={"fields": {"target_type": ["Unsupported target."]}})


@transaction.atomic
def submit_report(reporter, *, target_type, target_id, reason_code, description=""):
    _resolve_target(reporter, target_type, target_id)
    existing = Report.objects.filter(
        reporter=reporter,
        target_type=target_type,
        target_id=target_id,
        status__in=[Report.Status.OPEN, Report.Status.IN_REVIEW],
    ).first()
    if existing:
        return existing, False  # idempotent: one open report per reporter and target
    report = Report.objects.create(
        reporter=reporter,
        target_type=target_type,
        target_id=target_id,
        reason_code=reason_code,
        description=description,
    )
    audit.record(actor=reporter, action="report.submitted", resource=report)
    return report, True


# --- Moderation -------------------------------------------------------------


def require_moderator(user):
    from apps.identity import services as identity

    if not identity.is_moderator(user):
        raise Forbidden()


def moderation_queue(moderator, status=None):
    require_moderator(moderator)
    qs = Report.objects.select_related("reporter")
    if status:
        qs = qs.filter(status=status)
    return qs


def get_report_for_moderator(moderator, report_id):
    require_moderator(moderator)
    report = Report.objects.select_related("reporter").filter(id=report_id).first()
    if report is None:
        raise NotFound()
    return report


def target_preview(moderator, report):
    """Moderator view of the reported content. Message access is investigation access and
    is audited every time."""
    from apps.identity.models import User
    from apps.messaging.models import Message
    from apps.opportunities.models import Event, Opportunity
    from apps.social.models import Comment, Post

    require_moderator(moderator)
    t, tid = report.target_type, report.target_id
    if t == TargetType.USER:
        user = User.objects.filter(id=tid).first()
        return user and {"id": str(user.id), "display_name": user.display_name,
                         "account_status": user.account_status}
    if t == TargetType.POST:
        post = Post.objects.filter(id=tid).first()
        return post and {"id": str(post.id), "author_id": str(post.author_id), "body": post.body,
                         "status": post.status}
    if t == TargetType.COMMENT:
        c = Comment.objects.filter(id=tid).first()
        return c and {"id": str(c.id), "author_id": str(c.author_id), "body": c.body,
                      "status": c.status}
    if t == TargetType.MESSAGE:
        m = Message.objects.filter(id=tid).first()
        audit.record(actor=moderator, action="moderation.message_viewed", resource=m,
                     metadata={"report_id": str(report.id)})
        return m and {"id": str(m.id), "sender_id": str(m.sender_id),
                      "body": None if m.deleted_at else m.body}
    if t == TargetType.OPPORTUNITY:
        o = Opportunity.objects.filter(id=tid).first()
        return o and {"id": str(o.id), "title": o.title, "status": o.status,
                      "owner_id": str(o.owner_id)}
    if t == TargetType.EVENT:
        e = Event.objects.filter(id=tid).first()
        return e and {"id": str(e.id), "title": e.title, "status": e.status,
                      "owner_id": str(e.owner_id)}
    return None


_ALLOWED_ACTIONS = {
    TargetType.USER: {"suspend_user", "reinstate_user", "dismiss"},
    TargetType.POST: {"hide_content", "restore_content", "dismiss"},
    TargetType.COMMENT: {"hide_content", "restore_content", "dismiss"},
    TargetType.MESSAGE: {"suspend_user", "dismiss"},
    TargetType.OPPORTUNITY: {"close_listing", "dismiss"},
    TargetType.EVENT: {"dismiss"},
}


@transaction.atomic
def take_action(moderator, report, *, action_type, reason_code, note=""):
    from apps.identity import services as identity
    from apps.identity.models import AccountStatus, User
    from apps.messaging.models import Message
    from apps.opportunities import services as opportunities
    from apps.social import services as social

    require_moderator(moderator)
    report = Report.objects.select_for_update().get(pk=report.pk)
    if report.status in (Report.Status.RESOLVED, Report.Status.DISMISSED):
        raise Conflict("This report is already closed.", code="report_closed")
    if action_type not in _ALLOWED_ACTIONS.get(report.target_type, set()):
        raise ValidationFailed(
            details={"fields": {"action_type": ["Not allowed for this target type."]}}
        )

    t, tid = report.target_type, report.target_id
    if action_type in ("hide_content", "restore_content"):
        hidden = action_type == "hide_content"
        if t == TargetType.POST:
            social.moderate_post(moderator, tid, hidden=hidden)
        else:
            social.moderate_comment(moderator, tid, hidden=hidden)
    elif action_type in ("suspend_user", "reinstate_user"):
        user_id = tid
        if t == TargetType.MESSAGE:
            user_id = Message.objects.values_list("sender_id", flat=True).get(id=tid)
        user = User.objects.get(id=user_id)
        # Permission matrix: moderators only suspend if explicitly granted -> admin-only for MVP.
        if not identity.is_administrator(moderator):
            raise Forbidden("Only administrators can change account status.")
        status = AccountStatus.SUSPENDED if action_type == "suspend_user" else AccountStatus.ACTIVE
        identity.set_account_status(actor=moderator, user=user, status=status,
                                    reason_code=reason_code)
    elif action_type == "close_listing":
        opportunities.moderate_close_opportunity(moderator, tid)

    action = ModerationAction.objects.create(
        report=report,
        moderator=moderator,
        action_type=action_type,
        target_type=t,
        target_id=tid,
        reason_code=reason_code,
        note=note,
    )
    report.status = Report.Status.DISMISSED if action_type == "dismiss" else Report.Status.RESOLVED
    report.assigned_to = moderator
    report.resolution_note = note
    report.save(update_fields=["status", "assigned_to", "resolution_note", "updated_at"])
    audit.record(
        actor=moderator,
        action=f"moderation.{action_type}",
        resource=report,
        metadata={"target_type": t, "target_id": str(tid), "reason_code": reason_code},
    )
    return action

"""Outbox subscribers: translate domain events into in-app notifications.

Every handler is idempotent (deterministic dedup keys), because the outbox delivers
at least once.
"""

from apps.outbox import services as outbox

from .services import notify

STATUS_MESSAGES = {
    "shortlisted": "You were shortlisted",
    "accepted": "You were selected",
    "declined": "Your application was not selected",
}


def _opp_payload(p):
    return {"opportunity_id": p["opportunity_id"], "opportunity_title": p["opportunity_title"]}


def on_application_submitted(p):
    notify(
        recipient_id=p["owner_id"], actor_id=p["applicant_id"],
        notification_type="application.submitted",
        resource_type="application", resource_id=p["application_id"],
        payload=_opp_payload(p),
        dedup_key=f"application.submitted:{p['application_id']}",
    )


def on_application_status_changed(p):
    to = p["to_status"]
    if to == "withdrawn":
        recipient = p["owner_id"]
    elif to in STATUS_MESSAGES:
        recipient = p["applicant_id"]
    else:
        return
    notify(
        recipient_id=recipient, actor_id=p["actor_id"],
        notification_type=f"application.{to}",
        resource_type="application", resource_id=p["application_id"],
        payload={
            "opportunity_id": p["opportunity_id"],
            "opportunity_title": p["opportunity_title"],
            "status": to,
            "message": STATUS_MESSAGES.get(to, "An applicant withdrew"),
        },
        dedup_key=f"application.{to}:{p['application_id']}",
    )


def on_booking_cancelled(p):
    notify(
        recipient_id=p["recipient_id"], actor_id=p["actor_id"],
        notification_type="booking.cancelled",
        resource_type="booking", resource_id=p["booking_id"],
        payload=_opp_payload(p),
        dedup_key=f"booking.cancelled:{p['booking_id']}",
    )


def on_booking_outcome(p):
    notify(
        recipient_id=p["performer_id"], actor_id=p["actor_id"],
        notification_type=f"booking.{p['outcome']}",
        resource_type="booking", resource_id=p["booking_id"],
        payload=_opp_payload(p),
        dedup_key=f"booking.{p['outcome']}:{p['booking_id']}",
    )


def on_opportunity_cancelled(p):
    for recipient_id in p["recipient_ids"]:
        notify(
            recipient_id=recipient_id, actor_id=p["actor_id"],
            notification_type="opportunity.cancelled",
            resource_type="opportunity", resource_id=p["opportunity_id"],
            payload={"opportunity_title": p["title"]},
            dedup_key=f"opportunity.cancelled:{p['opportunity_id']}",
        )


def on_event_cancelled(p):
    for recipient_id in p["performer_ids"]:
        notify(
            recipient_id=recipient_id, actor_id=p["actor_id"],
            notification_type="event.cancelled",
            resource_type="event", resource_id=p["event_id"],
            payload={"event_title": p["title"]},
            dedup_key=f"event.cancelled:{p['event_id']}",
        )


def on_message_created(p):
    for recipient_id in p["recipient_ids"]:
        notify(
            recipient_id=recipient_id, actor_id=p["sender_id"],
            notification_type="message.received",
            resource_type="conversation", resource_id=p["conversation_id"],
            payload={},  # never copy message content into notifications
            dedup_key=f"message:{p['conversation_id']}",
            refresh=True,
        )


def on_post_liked(p):
    notify(
        recipient_id=p["author_id"], actor_id=p["actor_id"], notification_type="post.liked",
        resource_type="post", resource_id=p["post_id"],
        dedup_key=f"post.liked:{p['post_id']}:{p['actor_id']}",
    )


def on_post_commented(p):
    notify(
        recipient_id=p["author_id"], actor_id=p["actor_id"], notification_type="post.commented",
        resource_type="post", resource_id=p["post_id"],
        payload={"comment_id": p["comment_id"]},
        dedup_key=f"post.commented:{p['comment_id']}",
    )


def on_post_reposted(p):
    notify(
        recipient_id=p["author_id"], actor_id=p["actor_id"], notification_type="post.reposted",
        resource_type="post", resource_id=p["post_id"],
        dedup_key=f"post.reposted:{p['post_id']}:{p['actor_id']}",
    )


def on_user_followed(p):
    notify(
        recipient_id=p["followed_id"], actor_id=p["follower_id"], notification_type="user.followed",
        resource_type="user", resource_id=p["follower_id"],
        dedup_key=f"user.followed:{p['follower_id']}",
    )


def _venue_payload(p):
    return {"venue_id": p["venue_id"], "venue_name": p["venue_name"], "date": p["date"]}


def on_venue_booking_requested(p):
    for manager_id in p["manager_ids"]:
        notify(
            recipient_id=manager_id, actor_id=p["requester_id"],
            notification_type="venue_booking.requested",
            resource_type="venue_booking", resource_id=p["booking_id"],
            payload=_venue_payload(p),
            dedup_key=f"venue_booking.requested:{p['booking_id']}:{manager_id}",
        )


def on_venue_booking_status_changed(p):
    to, actor = p["to_status"], p["actor_id"]
    # Decisions go to the requester; a requester's cancellation goes to the managers.
    recipients = p["manager_ids"] if actor == p["requester_id"] else [p["requester_id"]]
    for recipient in recipients:
        notify(
            recipient_id=recipient, actor_id=actor,
            notification_type=f"venue_booking.{to}",
            resource_type="venue_booking", resource_id=p["booking_id"],
            payload=_venue_payload(p),
            dedup_key=f"venue_booking.{to}:{p['booking_id']}:{recipient}",
        )


def register():
    outbox.subscribe("application.submitted", on_application_submitted)
    outbox.subscribe("application.status_changed", on_application_status_changed)
    outbox.subscribe("booking.cancelled", on_booking_cancelled)
    outbox.subscribe("booking.outcome_recorded", on_booking_outcome)
    outbox.subscribe("opportunity.cancelled", on_opportunity_cancelled)
    outbox.subscribe("event.cancelled", on_event_cancelled)
    outbox.subscribe("message.created", on_message_created)
    outbox.subscribe("post.liked", on_post_liked)
    outbox.subscribe("post.commented", on_post_commented)
    outbox.subscribe("post.reposted", on_post_reposted)
    outbox.subscribe("user.followed", on_user_followed)
    outbox.subscribe("venue_booking.requested", on_venue_booking_requested)
    outbox.subscribe("venue_booking.status_changed", on_venue_booking_status_changed)

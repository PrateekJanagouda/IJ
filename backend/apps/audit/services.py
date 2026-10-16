"""Audit trail. Written synchronously inside the caller's transaction so the record
commits (or rolls back) together with the action it describes."""

from shared.middleware import get_request_id

from .models import AuditEvent


def _resource_type(resource):
    return resource._meta.model_name if resource is not None else ""


def record(*, actor, action, resource=None, outcome="success", metadata=None, actor_type="user"):
    return AuditEvent.objects.create(
        actor=actor if actor is not None and actor.is_authenticated else None,
        actor_type=actor_type if actor is not None else AuditEvent.ActorType.SYSTEM,
        action=action,
        resource_type=_resource_type(resource),
        resource_id=getattr(resource, "pk", None),
        outcome=outcome,
        request_id=get_request_id() or "",
        metadata=metadata or {},
    )

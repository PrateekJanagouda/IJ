"""Media domain: validate, store and read uploaded photos and videos."""

from apps.audit import services as audit
from shared.errors import NotFound, ValidationFailed

from .models import MediaAsset

MAX_BYTES = {MediaAsset.Kind.IMAGE: 8 * 1024 * 1024, MediaAsset.Kind.VIDEO: 25 * 1024 * 1024}

# Allowlist by file signature ("magic bytes"), never by the client's filename or declared
# Content-Type: both are attacker-controlled. SVG and HTML are deliberately absent, since a
# browser would run script embedded in them when served from our origin.
SIGNATURES = [
    (MediaAsset.Kind.IMAGE, "image/jpeg", lambda h: h[:3] == b"\xff\xd8\xff"),
    (MediaAsset.Kind.IMAGE, "image/png", lambda h: h[:8] == b"\x89PNG\r\n\x1a\n"),
    (MediaAsset.Kind.IMAGE, "image/gif", lambda h: h[:6] in (b"GIF87a", b"GIF89a")),
    (MediaAsset.Kind.IMAGE, "image/webp", lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP"),
    (MediaAsset.Kind.VIDEO, "video/webm", lambda h: h[:4] == b"\x1a\x45\xdf\xa3"),
    (MediaAsset.Kind.VIDEO, "video/quicktime", lambda h: h[4:8] == b"ftyp" and h[8:10] == b"qt"),
    (MediaAsset.Kind.VIDEO, "video/mp4", lambda h: h[4:8] == b"ftyp"),
]


def sniff(head):
    for kind, content_type, matches in SIGNATURES:
        if matches(head):
            return kind, content_type
    return None


def store(actor, upload):
    head = upload.read(16)
    upload.seek(0)
    found = sniff(head)
    if found is None:
        raise ValidationFailed(
            "Upload a photo (JPEG, PNG, WebP, GIF) or a video (MP4, MOV, WebM).",
            details={"fields": {"file": ["Unsupported file type."]}},
        )
    kind, content_type = found
    if upload.size > MAX_BYTES[kind]:
        limit = MAX_BYTES[kind] // (1024 * 1024)
        raise ValidationFailed(
            f"That {kind} is too large. The limit is {limit} MB.",
            details={"fields": {"file": [f"Max {limit} MB."]}},
        )
    asset = MediaAsset.objects.create(
        owner=actor, kind=kind, content_type=content_type, size=upload.size, data=upload.read(),
    )
    audit.record(actor=actor, action="media.uploaded", resource=asset,
                 metadata={"kind": kind, "size": upload.size})
    return asset


def get_asset(asset_id):
    asset = MediaAsset.objects.filter(id=asset_id).first()
    if asset is None:
        raise NotFound("Media not found.")
    return asset


def owned_assets(actor, ids, *, limit):
    """Resolve ids the actor uploaded, keeping the given order. Rejects anyone else's."""
    ids = list(dict.fromkeys(ids))
    if len(ids) > limit:
        raise ValidationFailed(f"Attach at most {limit} files.")
    assets = {a.id: a for a in MediaAsset.objects.filter(id__in=ids, owner=actor).defer("data")}
    if len(assets) != len(ids):
        raise ValidationFailed("One of the attached files was not found.")
    return [assets[i] for i in ids]


def url_for(asset_id):
    return f"/api/v1/media/{asset_id}/"

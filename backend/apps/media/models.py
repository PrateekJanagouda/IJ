from django.conf import settings
from django.db import models

from shared.models import UUIDModel


class MediaAsset(UUIDModel):
    """An uploaded photo or video.

    Bytes live in Postgres for now: the free host's disk is wiped on every restart, the
    database is not. Moving to object storage (S3/R2) later only changes `services.store`
    and `services.read`; callers keep using asset ids and `/media/<id>/` URLs.
    """

    class Kind(models.TextChoices):
        IMAGE = "image"
        VIDEO = "video"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "media_assets"
        indexes = [models.Index(fields=["owner", "-created_at"])]

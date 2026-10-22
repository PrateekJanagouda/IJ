import re

from django.http import HttpResponse
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from shared.errors import NotFound
from shared.throttling import WriteScopedThrottleMixin

from . import services
from .models import MediaAsset


class MediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MediaAsset
        fields = ["id", "kind", "content_type", "size", "url", "created_at"]
        read_only_fields = fields

    def get_url(self, asset) -> str:
        return services.url_for(asset.id)


class MediaUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class MediaUploadView(WriteScopedThrottleMixin, GenericAPIView):
    """Upload one photo or video (multipart field `file`). Attach it by id to a post or venue."""

    parser_classes = [MultiPartParser]
    serializer_class = MediaSerializer
    throttle_scope = "media"

    @extend_schema(request={"multipart/form-data": MediaUploadSerializer},
                   responses=MediaSerializer)
    def post(self, request):
        data = MediaUploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        asset = services.store(request.user, data.validated_data["file"])
        return Response(self.get_serializer(asset).data, status=status.HTTP_201_CREATED)


RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


@require_GET
def serve(request, asset_id):
    """Public, immutable bytes. Supports Range so phones can stream and seek in videos."""
    try:
        asset = services.get_asset(asset_id)
    except NotFound:
        return HttpResponse(status=404)
    data = bytes(asset.data)
    total = len(data)
    match = RANGE.match(request.headers.get("Range", ""))
    if match and (match[1] or match[2]):
        if match[1]:
            start = int(match[1])
            end = min(int(match[2]), total - 1) if match[2] else total - 1
        else:  # suffix range: the last N bytes
            start, end = max(0, total - int(match[2])), total - 1
        if start > end or start >= total:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{total}"
            return response
        response = HttpResponse(data[start:end + 1], status=206, content_type=asset.content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{total}"
    else:
        response = HttpResponse(data, content_type=asset.content_type)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Disposition"] = "inline"
    return response

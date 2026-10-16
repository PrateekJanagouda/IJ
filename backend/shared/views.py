from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.serializers import StatusSerializer


class HealthView(APIView):
    """Liveness: the process is up."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(responses=StatusSerializer)
    def get(self, request):
        return Response({"status": "ok"})


class ReadinessView(HealthView):
    """Readiness: dependencies needed to serve traffic are reachable."""

    @extend_schema(responses=StatusSerializer)
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response({"status": "unavailable", "database": "error"}, status=503)
        return Response({"status": "ok", "database": "ok"})

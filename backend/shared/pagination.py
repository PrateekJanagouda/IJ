from rest_framework.pagination import CursorPagination


class CreatedAtCursorPagination(CursorPagination):
    """Newest-first cursor pagination with an immutable tie-breaker (id)."""

    ordering = ("-created_at", "-id")
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"


class OldestFirstCursorPagination(CreatedAtCursorPagination):
    ordering = ("created_at", "id")

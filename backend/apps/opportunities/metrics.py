"""Pilot funnel: listing -> application -> selection -> confirmation -> completion."""

from django.db.models import CharField, Count, Value
from django.db.models.functions import Cast, Concat, TruncMonth

from .models import Application, Booking, Opportunity


def _by_month(qs, field, counted=None):
    counted = counted or Count("id")
    rows = qs.annotate(month=TruncMonth(field)).values("month").annotate(n=counted).order_by()
    return {row["month"].date().isoformat(): row["n"] for row in rows if row["month"]}


def funnel_by_month():
    completed = Booking.objects.filter(status=Booking.Status.COMPLETED)
    # North-star: unique artist->organizer pairs with a completed performance in the month,
    # so one booking is never double-counted across status changes.
    pair = Concat(
        Cast("performer_id", CharField()), Value(":"), Cast("opportunity__owner_id", CharField())
    )
    series = {
        "listings_published": _by_month(
            Opportunity.objects.filter(published_at__isnull=False), "published_at"
        ),
        "applications_submitted": _by_month(Application.objects.all(), "submitted_at"),
        "applications_accepted": _by_month(
            Application.objects.filter(status=Application.Status.ACCEPTED), "decided_at"
        ),
        "bookings_confirmed": _by_month(Booking.objects.all(), "selected_at"),
        "performances_completed": _by_month(completed, "completed_at"),
        "successful_connections": _by_month(
            completed, "completed_at", Count(pair, distinct=True)
        ),
    }
    months = sorted({m for s in series.values() for m in s})
    return [{"month": m, **{k: v.get(m, 0) for k, v in series.items()}} for m in months]

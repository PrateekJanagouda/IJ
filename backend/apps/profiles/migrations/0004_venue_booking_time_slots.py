"""Venue bookings move from whole dates to time slots.

Order matters: add nullable columns, backfill existing date-only rows (as 6pm-11pm
venue-local), make them required, then swap the per-date unique constraint for an
exclusion constraint on overlapping time ranges (which needs btree_gist for the
venue equality part of the GiST index).
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import django.contrib.postgres.constraints
from django.contrib.postgres.fields import RangeOperators
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models

import apps.profiles.models

VENUE_TZ = ZoneInfo("Asia/Kolkata")


def backfill_slots(apps, schema_editor):
    VenueBooking = apps.get_model("profiles", "VenueBooking")
    for b in VenueBooking.objects.filter(starts_at__isnull=True):
        b.starts_at = datetime.combine(b.date, time(18, 0), VENUE_TZ)
        b.ends_at = datetime.combine(b.date, time(23, 0), VENUE_TZ)
        b.save(update_fields=["starts_at", "ends_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0003_venue_amenities_venue_currency_venue_headline_and_more"),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.RemoveConstraint(model_name="venuebooking", name="uniq_venue_date_taken"),
        migrations.RemoveConstraint(model_name="venuebooking", name="uniq_open_venue_request"),
        migrations.AddField(model_name="venuebooking", name="starts_at",
                            field=models.DateTimeField(null=True)),
        migrations.AddField(model_name="venuebooking", name="ends_at",
                            field=models.DateTimeField(null=True)),
        migrations.RunPython(backfill_slots, migrations.RunPython.noop),
        migrations.AlterField(model_name="venuebooking", name="starts_at",
                              field=models.DateTimeField()),
        migrations.AlterField(model_name="venuebooking", name="ends_at",
                              field=models.DateTimeField()),
        migrations.AddIndex(
            model_name="venuebooking",
            index=models.Index(fields=["venue", "starts_at"], name="venue_booki_venue_i_7ff624_idx"),
        ),
        migrations.AddConstraint(
            model_name="venuebooking",
            constraint=models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")),
                                              name="venue_booking_ends_after_start"),
        ),
        migrations.AddConstraint(
            model_name="venuebooking",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                condition=models.Q(status__in=["confirmed", "blocked"]),
                expressions=[("venue", RangeOperators.EQUAL),
                             (apps.profiles.models.TsTzRange("starts_at", "ends_at"),
                              RangeOperators.OVERLAPS)],
                name="no_overlapping_venue_slots",
            ),
        ),
        migrations.AddConstraint(
            model_name="venuebooking",
            constraint=models.UniqueConstraint(condition=models.Q(status="requested"),
                                               fields=("venue", "requester", "starts_at"),
                                               name="uniq_open_venue_request"),
        ),
    ]

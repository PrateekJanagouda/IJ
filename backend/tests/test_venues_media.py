from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.identity.models import Role
from apps.notifications.models import Notification

from .conftest import make_user

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200


def upload(client, content, name="f.bin"):
    return client.post("/api/v1/media/", {"file": SimpleUploadedFile(name, content)},
                       format="multipart")


def day(n):
    return (timezone.localdate() + timedelta(days=n)).isoformat()


@pytest.fixture
def venue_owner(db):
    return make_user("venue@example.com", Role.VENUE, name="Vik Venue")


@pytest.fixture
def venue(client_for, venue_owner):
    r = client_for(venue_owner).post("/api/v1/venues/", {
        "name": "The Loft", "headline": "Intimate 120-cap listening room", "city": "Bengaluru",
        "capacity": 120, "starting_price": "15000", "payment_terms": "50% advance via UPI.",
    }, format="json")
    assert r.status_code == 201, r.data
    return r.data


# --- Media ------------------------------------------------------------------


def test_upload_is_sniffed_by_content_not_name(client_for, artist, anon):
    c = client_for(artist)
    r = upload(c, PNG, "holiday.exe")
    assert r.status_code == 201 and r.data["kind"] == "image"
    assert r.data["content_type"] == "image/png"
    assert upload(c, b"<svg onload=alert(1)>", "x.png").status_code == 400  # no SVG/HTML
    assert upload(anon, PNG).status_code in (401, 403)

    got = anon.get(r.data["url"])  # public, immutable bytes
    assert got.status_code == 200 and got.content == PNG
    assert got["Content-Type"] == "image/png" and got["X-Content-Type-Options"] == "nosniff"


def test_video_range_requests_for_streaming(client_for, artist, anon):
    r = upload(client_for(artist), MP4)
    assert r.data["kind"] == "video"
    part = anon.get(r.data["url"], HTTP_RANGE="bytes=4-11")
    assert part.status_code == 206 and part.content == b"ftypmp42"
    assert part["Content-Range"] == f"bytes 4-11/{len(MP4)}"
    assert anon.get(r.data["url"], HTTP_RANGE=f"bytes={len(MP4)}-").status_code == 416


def test_oversized_upload_rejected(client_for, artist, settings, monkeypatch):
    from apps.media import services

    monkeypatch.setitem(services.MAX_BYTES, "image", 10)
    assert upload(client_for(artist), PNG).status_code == 400


def test_post_with_photos_and_ownership(client_for, artist, member, anon):
    a, m = client_for(artist), client_for(member)
    photo = upload(a, PNG).data
    r = a.post("/api/v1/posts/", {"body": "", "media_ids": [photo["id"]]}, format="json")
    assert r.status_code == 201, r.data
    assert [x["id"] for x in r.data["media"]] == [photo["id"]]
    feed = anon.get("/api/v1/feed/discover/").data["results"]
    assert feed[0]["media"][0]["url"] == photo["url"]

    # Someone else's upload can't be attached; an empty post is still refused.
    assert m.post("/api/v1/posts/", {"media_ids": [photo["id"]]}, format="json").status_code == 400
    assert m.post("/api/v1/posts/", {"body": "  "}, format="json").status_code == 400


# --- Venues -----------------------------------------------------------------


def test_venue_listing_with_pricing_and_photos(client_for, venue_owner, anon, organizer, artist):
    c = client_for(venue_owner)
    photo = upload(c, PNG).data
    r = c.post("/api/v1/venues/", {"name": "Rooftop", "photo_ids": [photo["id"]],
                                   "payment_terms": "Full payment a week before."}, format="json")
    assert r.status_code == 201
    listed = anon.get("/api/v1/venues/").data["results"][0]
    assert listed["photos"][0]["url"] == photo["url"]
    assert listed["payment_terms"] == "Full payment a week before."
    assert listed["managers"][0]["id"] == str(venue_owner.id)
    # Artists can't list venues; organizers and venue accounts can.
    create = lambda u: client_for(u).post("/api/v1/venues/", {"name": "x"}, format="json")  # noqa: E731
    assert create(artist).status_code == 403
    assert create(organizer).status_code == 201


def test_request_confirm_flow_auto_declines_rivals(client_for, venue, venue_owner, organizer,
                                                   organizer2, run_outbox):
    o1, o2, v = client_for(organizer), client_for(organizer2), client_for(venue_owner)
    url = f"/api/v1/venues/{venue['id']}/bookings/"
    b1 = o1.post(url, {"date": day(10), "message": "Album launch", "expected_headcount": 90},
                 format="json")
    assert b1.status_code == 201 and b1.data["status"] == "requested"
    assert o1.post(url, {"date": day(10)}, format="json").status_code == 409  # one open ask
    b2 = o2.post(url, {"date": day(10)}, format="json")
    assert b2.status_code == 201
    run_outbox()
    assert Notification.objects.filter(recipient=venue_owner,
                                       notification_type="venue_booking.requested").count() == 2

    # Only the venue sees requests and decides them.
    assert o1.get(url).status_code == 403
    assert o2.post(f"/api/v1/venue-bookings/{b1.data['id']}/confirm/").status_code == 404
    assert len(v.get(url).data) == 2

    r = v.post(f"/api/v1/venue-bookings/{b1.data['id']}/confirm/")
    assert r.status_code == 200 and r.data["status"] == "confirmed"
    mine2 = o2.get("/api/v1/venue-bookings/mine/").data
    assert mine2[0]["status"] == "declined"  # rival request closed automatically
    run_outbox()
    assert Notification.objects.filter(recipient=organizer,
                                       notification_type="venue_booking.confirmed").exists()
    assert Notification.objects.filter(recipient=organizer2,
                                       notification_type="venue_booking.declined").exists()

    # The date is now taken for everyone.
    assert o2.post(url, {"date": day(10)}, format="json").status_code == 409
    avail = client_for().get(f"/api/v1/venues/{venue['id']}/availability/?days=30").data
    assert {"date": day(10), "status": "booked"} in avail["days"]


def test_availability_shows_your_requests_and_blocks(client_for, venue, venue_owner, organizer):
    o, v = client_for(organizer), client_for(venue_owner)
    o.post(f"/api/v1/venues/{venue['id']}/bookings/", {"date": day(3)}, format="json")
    blocked = v.post(f"/api/v1/venues/{venue['id']}/blocks/", {"date": day(5)}, format="json")
    assert blocked.status_code == 201 and blocked.data["status"] == "blocked"
    assert v.post(f"/api/v1/venues/{venue['id']}/blocks/", {"date": day(5)},
                  format="json").status_code == 409

    path = f"/api/v1/venues/{venue['id']}/availability/?days=14"
    days = {d["date"]: d["status"] for d in o.get(path).data["days"]}
    assert days == {day(3): "requested_by_you", day(5): "blocked"}
    days = {d["date"]: d["status"] for d in v.get(path).data["days"]}
    assert days == {day(3): "has_requests", day(5): "blocked"}
    assert client_for().get(path).data["days"] == [{"date": day(5), "status": "blocked"}]

    # Unblocking frees the date again.
    assert v.post(f"/api/v1/venue-bookings/{blocked.data['id']}/cancel/").status_code == 200
    assert o.post(f"/api/v1/venues/{venue['id']}/bookings/", {"date": day(5)},
                  format="json").status_code == 201


def test_booking_rules(client_for, venue, venue_owner, organizer, member):
    o, v = client_for(organizer), client_for(venue_owner)
    url = f"/api/v1/venues/{venue['id']}/bookings/"
    assert o.post(url, {"date": day(-1)}, format="json").status_code == 400  # past
    assert o.post(url, {"date": day(400)}, format="json").status_code == 400  # too far
    assert v.post(url, {"date": day(2)}, format="json").status_code == 409  # own venue
    assert client_for().post(url, {"date": day(2)}, format="json").status_code in (401, 403)

    b = o.post(url, {"date": day(2)}, format="json").data
    assert client_for(member).post(f"/api/v1/venue-bookings/{b['id']}/cancel/").status_code == 404
    assert o.post(f"/api/v1/venue-bookings/{b['id']}/cancel/").status_code == 200
    assert v.post(f"/api/v1/venue-bookings/{b['id']}/confirm/").status_code == 409  # cancelled

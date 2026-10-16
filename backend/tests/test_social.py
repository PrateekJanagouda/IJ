import pytest

from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def post(client, body="Hello", visibility="public"):
    r = client.post("/api/v1/posts/", {"body": body, "visibility": visibility}, format="json")
    assert r.status_code == 201, r.data
    return r.data


def test_follow_feed_like_comment_flow(client_for, artist, member, run_outbox):
    a, m = client_for(artist), client_for(member)
    p = post(a, "New single out!")
    assert m.get("/api/v1/feed/").data["results"] == []
    assert m.post(f"/api/v1/users/{artist.id}/follow/").status_code == 201
    assert m.post(f"/api/v1/users/{artist.id}/follow/").status_code == 200  # idempotent
    feed = m.get("/api/v1/feed/").data["results"]
    assert [x["id"] for x in feed] == [p["id"]]

    assert m.post(f"/api/v1/posts/{p['id']}/like/").status_code == 201
    assert m.post(f"/api/v1/posts/{p['id']}/like/").status_code == 200  # no duplicate likes
    m.post(f"/api/v1/posts/{p['id']}/comments/", {"body": "Love it"}, format="json")
    detail = m.get(f"/api/v1/posts/{p['id']}/").data
    assert detail["like_count"] == 1 and detail["comment_count"] == 1
    assert detail["viewer_has_liked"] is True
    assert detail["share_url"].endswith(f"/posts/{p['id']}")

    run_outbox()
    types = set(Notification.objects.filter(recipient=artist)
                .values_list("notification_type", flat=True))
    assert types == {"user.followed", "post.liked", "post.commented"}


def test_followers_only_posts_and_share_links_respect_visibility(client_for, artist, member,
                                                                 anon):
    private = post(client_for(artist), "Fans only", visibility="followers")
    assert anon.get(f"/api/v1/posts/{private['id']}/").status_code == 404
    assert client_for(member).get(f"/api/v1/posts/{private['id']}/").status_code == 404
    client_for(member).post(f"/api/v1/users/{artist.id}/follow/")
    assert client_for(member).get(f"/api/v1/posts/{private['id']}/").status_code == 200
    r = client_for(member).post(f"/api/v1/posts/{private['id']}/repost/")
    assert r.status_code == 409 and r.data["error"]["code"] == "not_shareable"


def test_repost_points_at_original_and_is_unique(client_for, artist, member, artist2):
    original = post(client_for(artist), "Original")
    r = client_for(member).post(f"/api/v1/posts/{original['id']}/repost/", {"body": "Check this"},
                                format="json")
    assert r.status_code == 201 and r.data["repost_of"]["id"] == original["id"]
    again = client_for(member).post(f"/api/v1/posts/{original['id']}/repost/")
    assert again.status_code == 409
    # Reposting a repost targets the source post.
    r2 = client_for(artist2).post(f"/api/v1/posts/{r.data['id']}/repost/")
    assert r2.data["repost_of"]["id"] == original["id"]
    assert client_for(artist).post(f"/api/v1/posts/{original['id']}/repost/").status_code == 409


def test_only_author_edits_or_deletes(client_for, artist, member, anon):
    p = post(client_for(artist))
    assert client_for(member).patch(f"/api/v1/posts/{p['id']}/", {"body": "hacked"},
                                    format="json").status_code == 403
    assert client_for(member).delete(f"/api/v1/posts/{p['id']}/").status_code == 403
    assert client_for(artist).patch(f"/api/v1/posts/{p['id']}/", {"body": "edited"},
                                    format="json").data["body"] == "edited"
    assert client_for(artist).delete(f"/api/v1/posts/{p['id']}/").status_code == 204
    assert anon.get(f"/api/v1/posts/{p['id']}/").status_code == 404


def test_comment_deletion_is_author_only(client_for, artist, member):
    p = post(client_for(artist))
    c = client_for(member).post(f"/api/v1/posts/{p['id']}/comments/", {"body": "hi"},
                                format="json").data
    assert client_for(artist).delete(f"/api/v1/comments/{c['id']}/").status_code == 403
    assert client_for(member).delete(f"/api/v1/comments/{c['id']}/").status_code == 204
    assert client_for(artist).get(f"/api/v1/posts/{p['id']}/comments/").data["results"] == []


def test_visitors_see_public_content_but_cannot_write(anon, client_for, artist):
    p = post(client_for(artist))
    assert anon.get("/api/v1/feed/discover/").data["results"][0]["id"] == p["id"]
    assert anon.get(f"/api/v1/posts/?author={artist.id}").status_code == 200
    assert anon.post("/api/v1/posts/", {"body": "x"}, format="json").status_code == 401
    assert anon.post(f"/api/v1/posts/{p['id']}/like/").status_code == 401
    assert anon.get("/api/v1/posts/?author=not-a-uuid").status_code == 400


def test_cannot_follow_self(client_for, artist):
    r = client_for(artist).post(f"/api/v1/users/{artist.id}/follow/")
    assert r.status_code == 400 and r.data["error"]["code"] == "self_follow"


def test_scoped_limits_apply_to_writes_but_reads_keep_global_limits(client_for, artist,
                                                                    monkeypatch, anon):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "posts", "2/hour")
    c = client_for(artist)
    assert [c.post("/api/v1/posts/", {"body": f"p{i}"}, format="json").status_code
            for i in range(3)] == [201, 201, 429]
    assert c.get("/api/v1/posts/").status_code == 200  # reading isn't blocked by post quota

    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "anon", "2/min")  # shared dict
    assert [anon.get("/api/v1/posts/").status_code for _ in range(3)] == [200, 200, 429]

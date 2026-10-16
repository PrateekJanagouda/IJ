# EQora

An artist network and gig marketplace for the live-performance ecosystem.

**Status:** MVP backend implemented (Django modular monolith). The web frontend (Next.js) is next.

- Product & scope: [`docs/product-requirements.md`](docs/product-requirements.md), [`docs/mvp-and-permissions.md`](docs/mvp-and-permissions.md)
- Architecture: [`docs/adr/ADR-001-modular-monolith.md`](docs/adr/ADR-001-modular-monolith.md), [`docs/architecture.md`](docs/architecture.md), [`docs/domain-design.md`](docs/domain-design.md)
- API & security: [`docs/api-and-security.md`](docs/api-and-security.md) · Schema: [`docs/database-design.md`](docs/database-design.md)
- **Decisions made to resolve open questions:** [`docs/mvp-decisions.md`](docs/mvp-decisions.md)

## Run it locally

With Docker:

```bash
cp .env.example .env
docker compose up --build          # API on http://localhost:8000
docker compose exec backend python manage.py createsuperuser
```

Without Docker (needs PostgreSQL 16; Redis optional):

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=true            # or copy values from ../.env.example
python manage.py migrate
python manage.py runserver
```

With `DJANGO_DEBUG=true` (or `EXPOSE_API_DOCS=true`), the interactive API docs are at `/api/v1/docs/`, and the OpenAPI schema at `/api/v1/schema/`.

## Test

```bash
cd backend
pytest                # 65 tests against real PostgreSQL, including concurrency races
ruff check .
```

## Backend layout

```text
backend/
  config/          settings, URLs, Celery
  shared/          error envelope, cursor pagination, session auth, request IDs
  apps/
    identity/      accounts, sessions, roles, password reset, account status
    profiles/      profiles, artist/organizer details, portfolio, venues + managers
    opportunities/ events, opportunities (slots), applications, bookings, funnel metrics
    social/        follows, posts, reposts, comments, likes, feeds
    messaging/     direct conversations, messages, unread state
    notifications/ in-app notifications (outbox subscribers)
    trust_safety/  blocks, reports, moderation actions
    audit/         append-only audit trail
    outbox/        transactional outbox + dispatcher
  tests/
```

Each module owns its tables and business rules in `services.py`. Views only parse input, call a service, and serialize the result. Other modules call a module's services and never write to its tables directly.

## How the critical paths are protected

| Risk | Protection | Proven by |
|---|---|---|
| Two organizers accept at once and overbook a slot | Opportunity row locked `FOR UPDATE` before the capacity check. Locks are always taken in the order opportunity → application. | `tests/test_concurrency.py` (6 concurrent accepts, capacity 2). The test fails if the lock is removed. |
| Double-submitted application | DB unique constraint. The losing race returns `409 already_applied`. | `test_concurrent_duplicate_applications_create_one_row` |
| Duplicate DM threads | Canonical `pair_key` unique constraint | `test_concurrent_conversation_starts_converge_on_one_conversation` |
| Notification lost or duplicated | Transactional outbox plus idempotent consumers (dedup keys) | `test_outbox_isolates_failing_handlers`, `test_repeated_accept_is_idempotent` |
| Cross-user access (IDOR) | Object-level checks in services. Private resources return 404 so their existence isn't revealed. | `test_applicants_cannot_see_each_other`, `test_non_participants_cannot_read_or_send`, … |
| Illegal state changes | Explicit transition tables. Final states are never overwritten. Every change records actor, reason, and from/to. | `test_invalid_and_stale_transitions_are_rejected` |

## API overview (`/api/v1/`)

| Area | Endpoints |
|---|---|
| Auth | `auth/csrf/` `auth/register/` `auth/login/` `auth/logout/` `auth/me/` `auth/me/roles/` `auth/password/change/` `auth/password/reset/` `auth/password/reset/confirm/` |
| Profiles | `profiles/` (search) `profiles/{id}/` `profiles/me/` `profiles/me/portfolio/` `genres/` `skills/` `venues/` `venues/{id}/managers/` |
| Events | `events/` `events/managed/` `events/{id}/` `…/publish/` `…/cancel/` `…/complete/` `…/opportunities/` `…/lineup/` |
| Opportunities | `opportunities/` (discovery filters: `q type compensation genre skill location starts_after starts_before event`) `opportunities/managed/` `opportunities/{id}/` `…/publish/` `…/close/` `…/cancel/` `…/complete/` `…/applications/` `…/bookings/` |
| Applications | `applications/mine/` `applications/{id}/` `…/history/` `…/shortlist/` `…/accept/` `…/decline/` `…/withdraw/` |
| Bookings | `bookings/mine/` `bookings/{id}/cancel/` `…/complete/` `…/no-show/` |
| Social | `feed/` `feed/discover/` `posts/` `posts/{id}/` `…/repost/` `…/like/` `…/comments/` `comments/{id}/` `users/{id}/follow/` `users/{id}/followers/` `users/{id}/following/` |
| Messaging | `conversations/` `conversations/unread-count/` `conversations/{id}/` `…/messages/` `…/read/` `…/archive/` `messages/{id}/` |
| Notifications | `notifications/` `notifications/unread-count/` `notifications/read-all/` `notifications/{id}/read/` |
| Safety | `reports/` `blocks/` `blocks/{user_id}/` `moderation/reports/` `moderation/reports/{id}/` `…/actions/` |
| Ops | `health/` `health/ready/` `metrics/funnel/` (admin) |

Every error uses the same envelope: `{"error": {"code", "message", "details", "request_id"}}`.

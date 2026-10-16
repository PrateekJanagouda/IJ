# EQora MVP Implementation Decisions

**Status:** Approved assumptions for the first implementation. Each is reversible; the "Change it by" column points at the single place to edit.
**Depends on:** all documents in `docs/`.

The design documents list open questions. Code cannot be written against an open question, so each one below was given a conservative default. Product owners should confirm or overturn these before the pilot.

## 1. Marketplace

| Question | Decision | Why | Change it by |
|---|---|---|---|
| What counts toward opportunity capacity? | One **accepted application = one seat**, whether it is a solo artist or a group act. | Applications are the only unit the system can see. Counting individual people needs member data we don't collect. | `Opportunity.capacity` docstring; `services.transition_application` |
| Can a booking be cancelled after acceptance? | Yes. **Either party** may cancel a `confirmed` booking (with a reason). The application stays `accepted` as history, and the seat is freed. | Real gigs fall through. Leaving the application decision untouched keeps the audit trail honest. | `services.cancel_booking` |
| Who records completion / no-show? | Organizer (or venue manager) only. | The organizer is the party who observes the outcome. | `services.record_booking_outcome` |
| Can an artist withdraw? | Only from `submitted` or `shortlisted`. After acceptance, they cancel the booking instead. | Keeps the application state machine and the booking lifecycle separate (`mvp-and-permissions.md` §5.5). | `APPLICANT_TRANSITIONS` |
| Reapplying after withdrawal? | Not allowed: one application per artist per opportunity. | Simplest rule that prevents spam. A DB unique constraint enforces it. | Relax the `uniq_application_per_opportunity` constraint |
| Event cancellation with live slots | The event becomes `cancelled`. Child opportunities are **not** cascaded: they are returned as "awaiting review" for the organizer to resolve one by one. They stop accepting applications immediately. If there are confirmed bookings, the request must include `confirm: true`. | Confirmed direction in `database-design.md` §3.4. | `services.cancel_event` |
| Opportunity cancellation | Cancels confirmed bookings in the same transaction and notifies all active applicants. Requires `confirm: true` when bookings exist. | The gig isn't happening, so leaving bookings "confirmed" would be false. | `services.cancel_opportunity` |
| Editing a published listing | Description, requirements, dates, deadline, location and capacity are editable. **Title, type and compensation are locked** after publishing. Capacity cannot go below current confirmed bookings. | Applicants applied on those terms, so changing pay after the fact is a trust problem. | `PUBLISHED_EDITABLE` |
| Publishing a slot under an event | The parent event must already be published. | Avoids public slots pointing at a draft event. | `services.publish_opportunity` |
| Event co-managers | No `event_managers` table yet. Event managers are the **owner** plus **managers of the event's venue**. | Satisfies "own or assigned" without building team management (P1). | `services.can_manage_event` (the one place to extend) |
| Venues | A venue is its own entity with explicit `VenueMembership`. Creating a venue makes you its manager, and managers can add other managers. You can only attach an event to a venue you manage. | Product requirement: venue access must be explicitly assigned, and a venue may be a team. | `profiles.services` |

## 2. Social

| Question | Decision | Why |
|---|---|---|
| Reposts | A repost is a `Post` with `repost_of` set, optionally with commentary. One active repost per user per post. No self-reposts. Reposting a repost targets the original. Only public posts can be reposted. | Keeps the feed to a single query over one table. This deliberately differs from the separate `post_reposts` table in `database-design.md`. |
| External sharing | API responses include a `share_url`. No server-side share rows are stored. | `database-design.md`: generating a URL needs no row. The URL resolves through normal visibility checks. |
| Post visibility | `public` or `followers`. | Matches the two audiences the product describes. |
| Feed | Chronological: your own posts plus posts from accounts you follow. There is also a public "discover" feed. | MVP calls for a simple, explainable feed. |
| Post media | Text and links only. | Rich media upload is P1. |
| Comment threading, comment likes | Not in MVP. | Not in the P0 list. |

## 3. Messaging

| Question | Decision |
|---|---|
| Who can start a DM? | Any active, signed-in user, unless either side has blocked the other. Starting conversations and sending messages are rate-limited. |
| Group chats, read receipts, typing, presence, attachments, E2EE | Not in MVP. |
| Unread state | Per-participant `last_read_at` is the single source of truth. There are no per-message receipts. |
| Real-time delivery | REST plus client polling for now. Messages are durable first; Channels/WebSockets can be added later as a delivery layer without changing the data model. |
| Message deletion | The sender soft-deletes for everyone. The row is kept for moderation, and the body is hidden in API responses. |
| Notifications | One notification per conversation, bumped back to unread on each new message. Notifications never contain the message body. |

## 4. Trust & safety

| Question | Decision |
|---|---|
| What does a block do? | It works both ways. It removes follows in both directions and hides profiles, posts and comments. It prevents following, liking, commenting, reposting, messaging, applying to the blocker's listings, and new notifications. Existing content and message history are kept. |
| Who can suspend accounts? | Administrators only. Moderators can hide/restore content and close listings. (Matrix: moderators suspend "only if explicitly granted.") |
| Moderator access to private messages | Only through a report on that message, and every view is audited (`moderation.message_viewed`). |
| Reporter privacy | Reports are visible only to their reporter and to moderators. |

## 5. Identity & platform

| Question | Decision |
|---|---|
| Login identifier | Email only, stored normalized (lowercase). |
| Roles | Artist and organizer are self-service (at signup or later). Moderator and administrator are granted by administrators only. Holding a role never grants access to someone else's resources. |
| Profile defaults | Profiles are `public` by default. Users can switch to `members` (signed-in users only) or `private`. Visitors can browse public profiles, posts, events and opportunities without an account. |
| Mobile / third-party clients | Not in MVP. Sessions plus CSRF cookies only. A token design is required before any native client. |
| Email delivery | Only password-reset emails. Notifications are in-app only (email is P1). |
| Account deletion | Deferred (required before public launch). Foreign keys to users are `PROTECT`, so nothing can be cascade-deleted by accident. |
| Audit writes | Written **synchronously, inside the business transaction**, not through the outbox. This differs from `domain-design.md` §2: an audit record that could be lost or delayed after the action commits is weaker evidence. |
| Side effects | Notifications go through a transactional outbox with idempotent consumers. The dispatcher runs `inline` (dev), via `celery` (prod), or `manual` (tests). |
| AI orchestration | Not built. AI is P2 in `mvp-and-permissions.md`. The service layer already has the shape agents will call through (typed commands, actor-scoped authorization). |
| Media storage | Not built (P1). Portfolio items are external `http(s)` links. |
| Feedback collection | Use an external form during the pilot. No in-app feature. |

## 6. Module naming

The docs use two naming schemes (`moderation`/`common` in Hour 3, versus `trust_safety`/`shared` in Hours 4 and 6). The code follows **Hours 4 and 6**: `identity`, `profiles`, `opportunities`, `social`, `messaging`, `notifications`, `trust_safety`, `audit`, `outbox`, plus a small `shared/` package. `authorization` is not a separate app: each domain owns its policy functions (`can_manage_event`, …) next to the rules they protect. `media` and `ai_orchestration` are deferred.

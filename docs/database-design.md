# EQura Database Design

**Status:** Proposed schema for review  
**Milestone:** Hour 6  
**Database:** PostgreSQL  
**Application architecture:** Django modular monolith  
**Scope:** Initial launch, including social networking, direct messaging, events, opportunities, applications, notifications, moderation, and AI orchestration foundations.

## 1. Design principles

1. PostgreSQL is the authoritative source for durable product data.
2. Every domain owns its entities and business rules.
3. Use relational constraints for invariants that must hold regardless of which application path writes data.
4. Use transactions for multi-row state transitions.
5. Use UUID primary keys for externally referenced entities to avoid exposing sequential IDs and to simplify future integrations. UUIDs are identifiers, not authorization controls.
6. Store timestamps as `timestamptz` in UTC.
7. Use explicit status fields and controlled transitions rather than arbitrary client updates.
8. Keep high-volume feed, messaging, and notification queries indexed around actual access patterns.
9. Avoid premature denormalization. Add counters, materialized views, or search infrastructure only after measuring bottlenecks.
10. Use Django migrations as the reviewed source of schema changes.

## 2. Ownership and shared conventions

Suggested Django apps:
- `identity`
- `authorization`
- `profiles`
- `social`
- `opportunities`
- `messaging`
- `notifications`
- `trust_safety`
- `media`
- `audit`
- `ai_orchestration`

Each app owns its tables. Cross-domain operations go through domain services. Cross-domain foreign keys are acceptable in a modular monolith when the relationship is stable and migration ownership is agreed, but another domain must not directly mutate an owner's data or bypass its business rules.

### Common fields

Use where appropriate:
- `id UUID PRIMARY KEY`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Do not add `updated_at` to immutable event records unless the record itself is meant to be editable. Set `updated_at` through a consistent application-level mechanism.

Use explicit deletion behavior for each foreign key. Prefer `PROTECT`/restrict for important historical relationships and carefully chosen `CASCADE` for dependent join rows. Account deletion should be a documented workflow, not an accidental chain of cascades.

## 3. Entity inventory

### 3.1 Identity and authorization

#### `users` (identity owner)
- `id UUID PK`
- `email_normalized VARCHAR UNIQUE NOT NULL` or a verified identifier model if multiple login methods are required
- `password_hash` managed by Django's user model
- `display_name VARCHAR NOT NULL`
- `account_status VARCHAR NOT NULL` (`active`, `suspended`, `pending_verification`, `deletion_pending`)
- `email_verified_at TIMESTAMPTZ NULL`
- `last_login_at TIMESTAMPTZ NULL`
- `created_at`, `updated_at`

Recommendation: use a custom Django user model from the start. One account may hold multiple roles. Decide whether email is the sole login identifier before implementation. Never store plaintext passwords.

#### `role_assignments`
- `id UUID PK`
- `user_id UUID FK -> users.id`
- `role VARCHAR NOT NULL` (`artist`, `organizer`, `venue_manager`, `moderator`, `administrator`)
- `scope_type VARCHAR NULL`
- `scope_id UUID NULL`
- `created_at`
- Unique constraint appropriate to the chosen scope model, e.g. `(user_id, role, scope_type, scope_id)`

Roles are not sufficient on their own for resource access. An organizer still needs ownership or explicit authorization for a particular event or opportunity. If the product requires only global roles initially, omit scope fields and add scoped grants only when the use case is defined.

### 3.2 Profiles and portfolio

#### `profiles`
- `id UUID PK`
- `user_id UUID UNIQUE FK -> users.id`
- `profile_type VARCHAR NOT NULL` (`artist`, `organizer`, `venue`)
- `display_name VARCHAR NOT NULL`
- `bio TEXT NULL`
- `location_label VARCHAR NULL` (avoid storing precise location unless needed and consented)
- `visibility VARCHAR NOT NULL` (`public`, `members`, `private`)
- `created_at`, `updated_at`

**Confirmed direction:** one account can be both artist and organizer. Use one core profile per user plus role-specific extension tables rather than constraining the account to a single `profile_type`. If the user can have multiple distinct organization/venue profiles, introduce organization or venue ownership/membership entities instead of assuming one extension row covers every organization.

#### `artist_profile_details`
- `profile_id UUID PK/FK -> profiles.id`
- `artist_name VARCHAR NULL`
- `genres` or normalized `genres` join table
- `skills` or normalized `skills` join table
- `experience_summary TEXT NULL`
- `booking_preferences JSONB NULL` only for flexible, low-query metadata

#### `organizer_profile_details`
- `profile_id UUID PK/FK -> profiles.id`
- `organization_name VARCHAR NULL`
- `verification_status VARCHAR NOT NULL DEFAULT 'unverified'`

#### `venue_profile_details`
- `profile_id UUID PK/FK -> profiles.id`
- `venue_name VARCHAR NOT NULL`
- `address`/venue coordinates only to the precision required for event logistics and with an explicit visibility policy
- `capacity INTEGER NULL CHECK (capacity IS NULL OR capacity > 0)`

#### `portfolio_items`
- `id UUID PK`
- `profile_id UUID FK -> profiles.id`
- `media_asset_id UUID FK -> media_assets.id`
- `title VARCHAR NOT NULL`
- `description TEXT NULL`
- `item_type VARCHAR NOT NULL` (`image`, `audio`, `video`, `external_link`)
- `position INTEGER NOT NULL DEFAULT 0`
- `visibility VARCHAR NOT NULL`
- `created_at`, `updated_at`

Index: `(profile_id, position, created_at)`.

#### `genres` / `profile_genres`
Use normalized tables if genre filtering and matching are core discovery features:
- `genres(id, slug UNIQUE, display_name)`
- `profile_genres(profile_id FK, genre_id FK, UNIQUE(profile_id, genre_id))`

Likewise add `skills`/`profile_skills` when they need structured filtering. Do not rely on unindexed JSON arrays for important filters.

### 3.3 Social network

#### `follows`
- `follower_user_id UUID FK -> users.id`
- `followed_user_id UUID FK -> users.id`
- `created_at`
- Composite PK or unique constraint `(follower_user_id, followed_user_id)`
- Check `follower_user_id <> followed_user_id`

Indexes:
- `(follower_user_id, created_at DESC, followed_user_id)` for following list
- `(followed_user_id, created_at DESC, follower_user_id)` for followers list

Private-account follow requests, if required, should be represented explicitly rather than inferred from this table.

#### `posts`
- `id UUID PK`
- `author_user_id UUID FK -> users.id`
- `body TEXT NULL`
- `visibility VARCHAR NOT NULL` (`public`, `followers`, `private`)
- `status VARCHAR NOT NULL` (`published`, `hidden`, `deleted`)
- `created_at`, `updated_at`

Check that a post has body text or at least one attached media item. This cross-table condition generally requires domain validation or a carefully designed transaction, not a simple row-level CHECK constraint.

Index: `(author_user_id, created_at DESC, id DESC)`.  
Feed index: `(created_at DESC, id DESC)` may help a broad public feed but is not a substitute for testing the actual feed query plan.

#### `post_media`
- `post_id UUID FK -> posts.id`
- `media_asset_id UUID FK -> media_assets.id`
- `position INTEGER NOT NULL`
- Unique `(post_id, position)` and unique `(post_id, media_asset_id)`

#### `comments`
- `id UUID PK`
- `post_id UUID FK -> posts.id`
- `author_user_id UUID FK -> users.id`
- `parent_comment_id UUID NULL FK -> comments.id` for threaded replies if allowed
- `body TEXT NOT NULL`
- `status VARCHAR NOT NULL` (`visible`, `hidden`, `deleted`)
- `created_at`, `updated_at`

Index: `(post_id, created_at ASC, id ASC)`. If threading is supported, add an index on `(parent_comment_id, created_at ASC)`.

#### `post_likes`
- `post_id UUID FK -> posts.id`
- `user_id UUID FK -> users.id`
- `created_at`
- Composite PK/unique `(post_id, user_id)`

Index `(user_id, created_at DESC)` for a user's liked posts if that view is exposed.

#### `comment_likes` (optional)
Only create if liking comments is in launch scope. Use unique `(comment_id, user_id)`.

#### `post_shares`
- `id UUID PK`
- `post_id UUID FK -> posts.id`
- `user_id UUID FK -> users.id`
- `share_type VARCHAR NOT NULL` (`internal`, `external_link`)
- `created_at`

**Confirmed direction:** sharing includes both external sharing and internal reposting. Keep `post_shares` only if external share actions need server-side analytics; generating/copying a URL does not inherently require a database row. Add a dedicated `post_reposts` table for internal reposts (`id`, `post_id`, `user_id`, optional `commentary`, `created_at`) with a uniqueness rule if a user may repost an original post only once. Decide whether self-reposts and quote-posts are allowed. Shared URLs must still enforce current visibility and authorization.

### 3.4 Events, opportunities, applications, and selections

**Core rule:** an event is the overall happening; an opportunity is an individually apply-able slot/role/gig. An event can have zero or many opportunities. An opportunity can be standalone with `event_id = NULL`. Applications always target one opportunity.

#### `events`
- `id UUID PK`
- `owner_user_id UUID FK -> users.id`
- `venue_profile_id UUID NULL FK -> profiles.id`
- `title VARCHAR NOT NULL`
- `description TEXT NULL`
- `starts_at TIMESTAMPTZ NULL`
- `ends_at TIMESTAMPTZ NULL`
- `timezone VARCHAR NOT NULL` (IANA zone, e.g. `Asia/Kolkata`)
- `location_text VARCHAR NULL`
- `visibility VARCHAR NOT NULL` (`public`, `unlisted`, `private`)
- `status VARCHAR NOT NULL` (`draft`, `published`, `cancelled`, `completed`)
- `published_at TIMESTAMPTZ NULL`
- `created_at`, `updated_at`

Checks:
- `ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at`
- Only authorized owners/managers may publish or cancel.
- **Confirmed direction:** event cancellation is a manual review workflow. Do not cascade-cancel or delete child opportunities/applications automatically. Record cancellation actor, timestamp and optional reason; provide a query for child opportunities still awaiting organizer review; notify applicants/booked performers when each affected opportunity is actually cancelled. Clarify whether the parent event can be marked cancelled while children remain unresolved.

Indexes:
- `(owner_user_id, created_at DESC)`
- `(status, starts_at)` for relevant public event discovery
- Consider a partial index for published events after query patterns are measured.

#### `event_managers` (optional if multiple organizers can manage one event)
- `event_id UUID FK -> events.id`
- `user_id UUID FK -> users.id`
- `permission_level VARCHAR NOT NULL`
- `created_at`
- Unique `(event_id, user_id)`

Add this if co-hosting, venue management, or event team permissions are in scope. Otherwise start with the owner and add the table when needed.

#### `opportunities`
- `id UUID PK`
- `event_id UUID NULL FK -> events.id`
- `owner_user_id UUID FK -> users.id`
- `title VARCHAR NOT NULL`
- `description TEXT NOT NULL`
- `opportunity_type VARCHAR NOT NULL` (e.g. `open_mic_slot`, `paid_gig`, `audition`, `band_slot`, `dj_slot`, `host_role`)
- `compensation_type VARCHAR NOT NULL` (`unpaid`, `paid`, `revenue_share`, `negotiable`)
- `compensation_amount NUMERIC(12,2) NULL`
- `currency CHAR(3) NULL`
- `capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity > 0)`
- `applications_open_at TIMESTAMPTZ NULL`
- `application_deadline TIMESTAMPTZ NULL`
- `starts_at TIMESTAMPTZ NULL`
- `ends_at TIMESTAMPTZ NULL`
- `timezone VARCHAR NOT NULL`
- `status VARCHAR NOT NULL` (`draft`, `published`, `paused`, `closed`, `cancelled`, `completed`)
- `requirements JSONB NULL` for flexible display-only requirements; use normalized eligibility tables for searchable criteria
- `created_at`, `updated_at`

Checks:
- Amount is nonnegative when present.
- Currency is present when an amount is present.
- `ends_at >= starts_at` when both exist.
- Domain service validates deadline order and whether the parent event permits publication.

Indexes:
- `(owner_user_id, created_at DESC)`
- `(event_id, status)`
- `(status, application_deadline)`
- A measured discovery index based on common filters, likely status + start date and structured category/genre relationships.

#### `opportunity_genres` / `opportunity_skills` (if needed)
Normalized many-to-many tables with composite unique constraints. Use these for matching and filters rather than querying unindexed JSON blobs.

#### `applications`
- `id UUID PK`
- `opportunity_id UUID FK -> opportunities.id`
- `applicant_user_id UUID FK -> users.id`
- `status VARCHAR NOT NULL` (`submitted`, `shortlisted`, `accepted`, `declined`, `withdrawn`)
- `cover_note TEXT NULL`
- `submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `decided_at TIMESTAMPTZ NULL`
- `decided_by_user_id UUID NULL FK -> users.id`
- `created_at`, `updated_at`
- Unique `(opportunity_id, applicant_user_id)`

Indexes:
- `(applicant_user_id, created_at DESC)` for artist applications
- `(opportunity_id, status, submitted_at)` for organizer review
- `(decided_by_user_id, decided_at DESC)` only if a real query needs it

**Confirmed direction:** accepting an application immediately confirms the booking, and an opportunity may select multiple performers. The acceptance endpoint must atomically mark the application `accepted` and create/activate the corresponding booking or performer-selection record. Use a transaction and row locking or an equivalent concurrency-safe strategy to ensure concurrent acceptances do not exceed capacity. A unique application constraint does not solve capacity races by itself. Clarify whether capacity counts individual performers, applications, or acts/groups, and define post-acceptance cancellation/revocation states.

#### `performer_selections` (recommended if accepted applications and booked performers must be distinct concepts)
- `id UUID PK`
- `opportunity_id UUID FK -> opportunities.id`
- `performer_user_id UUID FK -> users.id`
- `application_id UUID NULL FK -> applications.id`
- `status VARCHAR NOT NULL` (`selected`, `confirmed`, `cancelled`, `completed`, `no_show`)
- `selected_by_user_id UUID FK -> users.id`
- `selected_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `created_at`, `updated_at`

Acceptance immediately confirms the booking, so if booking lifecycle states such as `cancelled`, `completed`, or `no_show` are needed, retain this table and create the selection in the same transaction that accepts the application. Add constraints to prevent duplicate active selections for the same application and opportunity. Do not add a second pending performer-confirmation state. The capacity unit and post-acceptance cancellation rules still require clarification.

#### `event_cancellation_records` (optional)
Use an explicit record if cancellation reason, actor, timestamp, and propagation outcome must be retained. Do not cascade-delete applications when an event is cancelled.

### 3.5 Direct messaging

#### `conversations`
- `id UUID PK`
- `conversation_type VARCHAR NOT NULL` (`direct`; reserve `group` for later if group chat is not in scope)
- `created_by_user_id UUID FK -> users.id`
- `created_at`, `updated_at`
- Optional `last_message_at TIMESTAMPTZ NULL` as a denormalized list-ordering field maintained transactionally or through a reliable service.

#### `conversation_participants`
- `conversation_id UUID FK -> conversations.id`
- `user_id UUID FK -> users.id`
- `joined_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `last_read_at TIMESTAMPTZ NULL`
- `muted_at TIMESTAMPTZ NULL`
- `archived_at TIMESTAMPTZ NULL`
- Composite PK/unique `(conversation_id, user_id)`

Index `(user_id, archived_at, conversation_id)` for the inbox. For direct conversations, enforce a canonical participant-pair uniqueness rule. PostgreSQL cannot enforce “exactly two participant rows” with a simple row-level CHECK, so create direct conversations through a service that serializes creation and uses a dedicated canonical pair key/table or a deterministic participant-pair record. Do not rely only on a count check in application code under concurrency.

#### `messages`
- `id UUID PK`
- `conversation_id UUID FK -> conversations.id`
- `sender_user_id UUID FK -> users.id`
- `body TEXT NULL`
- `message_type VARCHAR NOT NULL DEFAULT 'text'` (`text`, `media`, `system`)
- `media_asset_id UUID NULL FK -> media_assets.id`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `edited_at TIMESTAMPTZ NULL`
- `deleted_at TIMESTAMPTZ NULL`

Validation: text messages must contain nonempty text; media messages must reference a valid authorized media asset. Enforce that the sender is a current participant in the conversation in the messaging service within the same transaction. A simple FK to `users` does not prove conversation membership.

Index `(conversation_id, created_at DESC, id DESC)` for message history. Consider `(sender_user_id, created_at DESC)` only if needed for moderation or account exports.

#### `message_receipts` (defer unless per-message receipts are required)
A participant-level `last_read_at` can support an initial unread approximation. If precise per-message read/delivery receipts are a launch requirement, add:
- `message_id UUID FK -> messages.id`
- `user_id UUID FK -> users.id`
- `delivered_at TIMESTAMPTZ NULL`
- `read_at TIMESTAMPTZ NULL`
- Unique `(message_id, user_id)`

Avoid maintaining both per-message receipts and participant `last_read_at` without defining which is authoritative.

### 3.6 Notifications

#### `notifications`
- `id UUID PK`
- `recipient_user_id UUID FK -> users.id`
- `actor_user_id UUID NULL FK -> users.id`
- `notification_type VARCHAR NOT NULL`
- `resource_type VARCHAR NULL`
- `resource_id UUID NULL`
- `deduplication_key VARCHAR NULL`
- `payload JSONB NOT NULL DEFAULT '{}'`
- `read_at TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

`resource_type` + `resource_id` is a polymorphic reference and does not receive a normal FK constraint. Keep payloads small and avoid embedding private message content. For critical resource links, validate resource access at read time.

Indexes:
- `(recipient_user_id, created_at DESC, id DESC)`
- Partial index `(recipient_user_id, created_at DESC) WHERE read_at IS NULL`
- Unique deduplication key where the intended scope is defined, e.g. `(recipient_user_id, deduplication_key)` with a partial condition for non-null keys.

#### `notification_preferences`
- `user_id UUID FK -> users.id`
- `notification_type VARCHAR`
- `in_app_enabled BOOLEAN NOT NULL DEFAULT true`
- `email_enabled BOOLEAN NOT NULL DEFAULT true`
- `created_at`, `updated_at`
- Unique `(user_id, notification_type)`

In-app notifications are required for launch. Email delivery can be enabled per type after product and deliverability decisions.

### 3.7 Trust and safety

#### `user_blocks`
- `blocker_user_id UUID FK -> users.id`
- `blocked_user_id UUID FK -> users.id`
- `created_at`
- Composite PK/unique `(blocker_user_id, blocked_user_id)`
- Check users differ

**Confirmed direction:** blocking prevents all relevant interactions. Apply block checks consistently to messaging, following, profiles/search/discovery, feeds, comments, likes, reposts, notifications and AI-triggered actions. Define how existing follows, messages, public content and active booking logistics behave. Do not delete historical content merely because a block is created.

#### `reports`
- `id UUID PK`
- `reporter_user_id UUID FK -> users.id`
- `target_type VARCHAR NOT NULL`
- `target_id UUID NOT NULL`
- `reason_code VARCHAR NOT NULL`
- `description TEXT NULL`
- `status VARCHAR NOT NULL` (`open`, `in_review`, `resolved`, `dismissed`)
- `created_at`, `updated_at`
- `assigned_to_user_id UUID NULL FK -> users.id`

Because target references are polymorphic, enforce target existence and access policy in a service layer. Add indexes on `(status, created_at)` and `(reporter_user_id, created_at DESC)`.

#### `moderation_actions`
- `id UUID PK`
- `case/report reference` using an explicit FK if actions belong to one report
- `moderator_user_id UUID FK -> users.id`
- `action_type VARCHAR NOT NULL`
- `target_type VARCHAR NOT NULL`
- `target_id UUID NOT NULL`
- `reason_code VARCHAR NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Restrict and audit moderator access. Keep an append-only history of decisions rather than silently overwriting past actions.

### 3.8 Media and audit

#### `media_assets`
- `id UUID PK`
- `owner_user_id UUID FK -> users.id`
- `storage_key VARCHAR UNIQUE NOT NULL`
- `media_type VARCHAR NOT NULL`
- `mime_type VARCHAR NOT NULL`
- `size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0)`
- `processing_status VARCHAR NOT NULL` (`pending`, `ready`, `rejected`, `failed`)
- `visibility VARCHAR NOT NULL`
- `created_at`, `updated_at`

Validate file contents, limits, authorization, and visibility before issuing upload credentials or serving files. Keep object storage keys private; use authorized URLs or controlled public delivery depending on visibility.

#### `audit_events`
- `id UUID PK`
- `actor_user_id UUID NULL FK -> users.id`
- `actor_type VARCHAR NOT NULL` (`user`, `system`, `agent`)
- `action VARCHAR NOT NULL`
- `resource_type VARCHAR NULL`
- `resource_id UUID NULL`
- `outcome VARCHAR NOT NULL`
- `request_id VARCHAR NULL`
- `agent_run_id UUID NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Avoid logging credentials, session tokens, full private message bodies, or unnecessary personal data. Restrict audit table access and define retention.

### 3.9 AI orchestration (minimal foundation)

#### `agent_runs`
- `id UUID PK`
- `agent_name VARCHAR NOT NULL`
- `initiating_user_id UUID NULL FK -> users.id`
- `status VARCHAR NOT NULL` (`queued`, `running`, `succeeded`, `failed`, `cancelled`, `awaiting_approval`)
- `input_summary JSONB NOT NULL DEFAULT '{}'` (minimize sensitive content)
- `result_summary JSONB NULL`
- `started_at TIMESTAMPTZ NULL`
- `finished_at TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

#### `agent_tool_executions`
- `id UUID PK`
- `agent_run_id UUID FK -> agent_runs.id`
- `tool_name VARCHAR NOT NULL`
- `actor_user_id UUID NULL FK -> users.id`
- `resource_type VARCHAR NULL`
- `resource_id UUID NULL`
- `status VARCHAR NOT NULL` (`requested`, `approved`, `executing`, `succeeded`, `failed`, `rejected`)
- `idempotency_key VARCHAR NULL`
- `input_summary JSONB NOT NULL DEFAULT '{}'`
- `output_summary JSONB NULL`
- `request_id VARCHAR NULL`
- `created_at`, `updated_at`

Unique constraints should be added for idempotency within a clearly defined scope. Do not store unrestricted raw prompts, secrets, or private user content by default.

#### `agent_approvals` (when confirmation-gated actions are implemented)
- `id UUID PK`
- `tool_execution_id UUID UNIQUE FK -> agent_tool_executions.id`
- `approver_user_id UUID FK -> users.id`
- `decision VARCHAR NOT NULL` (`approved`, `rejected`, `expired`)
- `approved_action_hash VARCHAR NOT NULL`
- `expires_at TIMESTAMPTZ NOT NULL`
- `decided_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Approval must be bound to the exact action/resource/payload and expire. Revalidate authorization and resource state when executing the action.

## 4. Relationship overview

```text
User
 ├── Profile
 │    └── Portfolio items ── Media assets
 ├── Role assignments
 ├── Posts ── Post media ── Media assets
 │    ├── Comments
 │    ├── Likes
 │    └── Shares
 ├── Follows (follower and followed)
 ├── Conversations ── Participants
 │    └── Messages ── optional Media asset
 ├── Notifications
 ├── Applications ── Opportunity
 ├── Blocks / Reports / Moderation references
 └── Agent runs ── Tool executions ── optional approvals

Event (owner, optional venue)
 └── zero or many Opportunities
      ├── zero or many Applications
      └── optional Performer selections

Standalone Opportunity: event_id = NULL
Application: always belongs to exactly one Opportunity
```

## 5. Critical integrity and concurrency rules

1. **Duplicate application:** unique `(opportunity_id, applicant_user_id)`.
2. **Self-follow and self-block:** CHECK constraint disallowing identical user IDs.
3. **Like uniqueness:** one like per user/post.
4. **Participant membership:** only conversation participants may read or send messages.
5. **Conversation creation:** enforce unique direct participant pairs under concurrency.
6. **Opportunity capacity:** acceptance/selection uses a transaction and row-level locking or another concurrency-safe reservation strategy. A uniqueness constraint on applications alone is insufficient.
7. **State transitions:** only allowed transitions are accepted by domain services, e.g. submitted → shortlisted/accepted/declined/withdrawn according to policy.
8. **Event cancellation:** never delete applications through FK cascade; explicitly update affected opportunities and notify impacted users.
9. **Notification delivery:** use a transactional outbox for critical side effects so the domain change and event record commit atomically.
10. **Idempotency:** duplicate requests and worker retries must not create duplicate applications, acceptances, notifications, or AI actions.
11. **Privacy filtering:** apply visibility, block, membership, and account-status checks in backend query/service paths.
12. **Polymorphic references:** notifications and reports with `(resource_type, resource_id)` need explicit service-level validation because they lack conventional FK integrity.

## 6. Initial index plan

Do not create every possible index speculatively. Start with these high-value patterns and validate using `EXPLAIN (ANALYZE, BUFFERS)` against representative data.

| Table | Index / constraint | Query it supports |
|---|---|---|
| `users` | Unique normalized login identifier | Login and account lookup |
| `follows` | Unique `(follower_user_id, followed_user_id)` | Prevent duplicate follows |
| `follows` | `(followed_user_id, created_at DESC)` | Follower list |
| `posts` | `(author_user_id, created_at DESC, id DESC)` | Profile timeline |
| `comments` | `(post_id, created_at, id)` | Post comments |
| `post_likes` | Unique `(post_id, user_id)` | Prevent duplicate likes |
| `events` | `(status, starts_at)` | Published event discovery |
| `opportunities` | `(status, application_deadline)` | Open opportunity discovery and deadline processing |
| `applications` | Unique `(opportunity_id, applicant_user_id)` | Prevent duplicate application |
| `applications` | `(opportunity_id, status, submitted_at)` | Organizer applicant review |
| `applications` | `(applicant_user_id, created_at DESC)` | Artist application history |
| `conversation_participants` | `(user_id, archived_at, conversation_id)` | Inbox |
| `messages` | `(conversation_id, created_at DESC, id DESC)` | Message history |
| `notifications` | `(recipient_user_id, created_at DESC, id DESC)` | Notification list |
| `notifications` | Partial `(recipient_user_id, created_at DESC) WHERE read_at IS NULL` | Unread notifications |
| `reports` | `(status, created_at)` | Moderation queue |

For full-text discovery, start with PostgreSQL full-text search and/or trigram indexes only after choosing searchable fields and testing query patterns. Do not add PostGIS until location-based discovery requirements justify it.

## 7. Deletion and retention

- Define whether account deletion anonymizes, soft-deletes, or removes each data category.
- Preserve required operational/audit records only where there is a valid retention basis.
- **Current decision:** account deletion policy is deferred. Do not implement a blanket destructive cascade from `users`; choose deletion/anonymization/retention rules before public launch. Do not accidentally cascade-delete application/booking history, moderation evidence, audit records, or financial records if later introduced.
- Remove or revoke access to media and invalidate public links when content is deleted or made private.
- Define message deletion semantics: sender-only soft deletion, deletion for all participants, retention for moderation, and export behavior.
- Make deletion jobs retryable and auditable. Include backups in the documented retention model.

## 8. Implementation sequence

1. Create a custom Django user model before the first migration.
2. Implement identity, roles/authorization, profiles, and media metadata.
3. Implement events, opportunities, applications, and transaction-safe selection.
4. Implement social relationships and posts/comments/likes/shares.
5. Implement conversations, participants, messages, and unread state.
6. Implement notifications and the transactional outbox.
7. Implement blocks, reports, moderation, and audit records.
8. Add minimal AI run/tool/approval tables when the first AI feature has a concrete use case.
9. Add indexes guided by real query plans and representative data.
10. Review migration reversibility, deletion policies, and authorization tests.

## 9. Decisions still required before final migrations

- Can a user manage multiple organizations or venues, or only their own organizer profile?
- Are profiles public by default, and can users make them private?
- Are group conversations excluded from launch? Recommended: yes, start with one-to-one.
- Are per-message read receipts required, or is per-conversation unread state sufficient?
- Can users add commentary to reposts, repost their own content, or quote-post?
- What counts toward opportunity capacity: individual people, applications, or acts/groups?
- Can artists cancel after acceptance, and can organizers revoke an accepted booking?
- Can an event be marked cancelled while child opportunities await manual review?
- What happens to existing follows/messages/content after a block?
- What are the retention and deletion rules for messages, reports, audit records, and account data? Account deletion policy is deferred but required before public launch.
- Which portfolio media types and file size limits are supported?
- Is precise location search needed at launch, and at what privacy precision?
- Will external payment or ticketing be part of the first release? If yes, a separate payment/ticket inventory design is required.

## 10. Acceptance criteria

The database design is ready to implement when:
- Each entity has a clear owning domain.
- Core relationships and unique constraints are reviewed.
- Application capacity and acceptance concurrency behavior is specified.
- Direct message membership and direct-conversation uniqueness are specified.
- Event cancellation and deletion semantics are explicit.
- The team resolves the launch-critical questions above or records approved assumptions.
- Initial Django migrations are reviewed and automated integrity/authorization tests are planned.

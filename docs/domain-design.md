# EQora Domain Design: Hour 4

## Objective

Define the planned Django domain modules, their data ownership and cross-domain rules, and the safe interaction model for future AI agents. EQora remains a modular monolith: logical Django apps in one backend project, not separate microservices.

## 1. Planned Django domain modules

| Django app | Owns | Notes |
|---|---|---|
| `identity` | User accounts, credentials, account status, authentication | The canonical identity for each person or organization account. |
| `authorization` | Role assignments, permissions, policy evaluation | Enforces resource-level permissions; frontend visibility is not authorization. |
| `profiles` | Artist, organizer and venue profiles; skills, genres, portfolio metadata | References user IDs owned by `identity`; does not duplicate credentials. |
| `social` | Posts, comments, likes, follow relationships, share records | Owns social interactions and feed inputs. |
| `opportunities` | Events, performance slots/opportunities, applications, selections | An event may have zero or more opportunities. A standalone opportunity is valid. Applications belong to an individual opportunity. |
| `messaging` | Conversations, participants, messages, read state, delivery metadata | Conversation access is checked for every read and write. |
| `notifications` | In-app notification records, unread state, preferences and delivery status | Receives domain events; does not own the underlying action. |
| `trust_safety` | User blocks, reports, moderation cases and moderation decisions | Supplies policy outcomes that other domains enforce. |
| `media` | Upload records, ownership metadata, processing status | Binary files live in object storage, not directly in relational rows. |
| `audit` | Security-sensitive and consequential action records | Records actor, action, resource, timestamp, outcome and relevant correlation IDs. Avoid logging secrets or unnecessary message contents. |
| `ai_orchestration` | Agent definitions, tool registry, run state, approvals, evaluation records | Calls approved application capabilities; does not bypass domain services. |

Infrastructure adapters such as email, object storage, search, background jobs and external APIs should be isolated behind interfaces. They are not owners of core business rules.

## 2. Ownership and cross-domain rules

### Ownership

- `identity` owns accounts and account status.
- `profiles` owns profile and portfolio metadata.
- `social` owns posts, comments, likes, follows and share records.
- `opportunities` owns event and opportunity lifecycle, applications, and performer selection.
- `messaging` owns conversations and messages.
- `notifications` owns notification delivery and read state.
- `trust_safety` owns blocks, reports and moderation cases.
- `media` owns upload metadata and processing state; object storage owns the file bytes.
- `audit` owns the audit trail.
- `ai_orchestration` owns agent runs, tool execution metadata and approvals, not the business resources those agents act upon.

### Cross-domain rules

1. A domain must not write directly to another domain's tables to perform a business operation. Use the owning domain's service interface.
2. Cross-domain references use stable IDs. Avoid duplicating credentials or mutable copies of another domain's source-of-truth data.
3. Keep transactions local wherever possible. A business state transition and its required outbox record should commit atomically.
4. Use domain events for side effects, for example `application.accepted`, `post.published`, `message.created` and `report.submitted`.
5. Use a transactional outbox for important events so a committed business action is not lost if event delivery fails. Consumers must be idempotent.
6. Recheck authorization and current resource state at the point of execution. Hiding a frontend control is not access control.
7. Apply trust-and-safety policies at relevant entry points, including messaging, following and content interactions.
8. Avoid circular imports and dependencies on private implementation details. Depend on stable service interfaces, command functions or event contracts.
9. Use pagination, rate limits and bounded queries for user-facing and agent-facing search tools.
10. Log consequential actions, but do not log credentials, tokens or unnecessary sensitive message content.

### Example: accepting an artist for a gig

1. An organizer requests acceptance for an application.
2. The `opportunities` service authenticates the actor and checks organizer permissions, application status, deadline and slot rules.
3. A database transaction updates the application/selection state and writes an outbox event.
4. A worker publishes the event. `notifications` creates an in-app notification, and `audit` records the consequential decision.
5. Retries must not accept the artist twice or create duplicate notifications. If the transaction fails, no success notification is sent.

## 3. AI agent interaction model

AI agents are controlled clients of EQora's backend capabilities. They may propose plans and choose approved tools, but normal backend services remain responsible for authorization, validation, persistence and business invariants.

### Execution path

1. An agent proposes a tool call.
2. `ai_orchestration` checks the allowlist, actor context, scope, limits and approval requirements.
3. A typed tool validates its input and invokes an application capability.
4. The domain service rechecks authorization and resource state.
5. The domain service performs the operation, using a transaction when needed.
6. The result, approval and audit metadata are recorded; side effects are emitted through domain events/outbox processing.

### Required tool contract

Every tool must define:

- Name, purpose and prohibited uses.
- Typed input/output schemas, size limits and allowed values.
- Actor identity, resource scope and authorization requirements.
- Domain validation and state-transition rules.
- Side-effect classification: read-only, reversible write or consequential write.
- Whether explicit user confirmation is required.
- Idempotency and retry behavior.
- Timeout and execution limits.
- Audit metadata and error behavior.

Agents must not receive raw database credentials, unrestricted SQL, arbitrary shell execution, unrestricted internal HTTP access, or a mechanism to bypass domain authorization. Give each agent only the minimum data and tools required for its task.

### Initial agent capabilities

| Agent | Allowed capabilities | Restrictions |
|---|---|---|
| Artist Discovery | Search public profiles and opportunities; rank matches | Do not expose private profile data or apply on behalf of an artist without authorization. |
| Event Planning | Read event details; draft schedules; suggest performers and slots | Publishing or inviting performers requires suitable permission and confirmation where configured. |
| Event Operations | Read event status; prepare reminders; identify missing information | Cannot cancel events or change bookings without authorization and required confirmation. |
| Messaging Assistant | Draft replies and summarize conversations the actor may access | Cannot send as a user unless explicitly authorized and confirmed under policy. |
| Trust & Safety Assistant | Triage reports, flag suspicious activity, recommend actions | High-impact enforcement decisions should be reviewed by an authorized moderator by default. |
| Analytics Assistant | Produce approved aggregate metrics and trend summaries | Cannot expose private user data or perform business mutations. |

### Confirmation policy

Typically safe for automatic execution: search public opportunities, rank matches, summarize permitted data, draft posts, and prepare event plans.

Require authorization and often explicit confirmation: publish a post or event, send a message, accept an application, invite performers, cancel an event, or impose a moderation action. Confirmation does not replace authorization. For sensitive operations, approval must be bound to the exact proposed action and resource state; stale approvals must be rejected.

### Implementation pattern

Begin with ordinary Python service functions exposed through typed tool definitions. Prefer explicit commands such as `submit_application`, `accept_application`, and `publish_event` over generic tools that execute arbitrary action names and payloads. Agent-generated arguments are untrusted input and must be validated.

Illustrative interface only:

```python
def search_opportunities(*, actor, filters):
    authorize(actor, "opportunities.search")
    validated_filters = validate_search_filters(filters)
    return opportunity_service.search(validated_filters)
```

The orchestration layer and domain service should each enforce the relevant security boundary. The model's instructions are not a substitute for backend policy enforcement.

## 4. Suggested backend layout

```text
backend/
  config/                 # Django project settings, URLs, ASGI/WSGI
  apps/
    identity/
    authorization/
    profiles/
    social/
    opportunities/
    messaging/
    notifications/
    trust_safety/
    media/
    audit/
    ai_orchestration/
  shared/                 # Small shared primitives and stable contracts only
  integrations/            # Email, object storage, search and external APIs
  tests/
```

Keep `shared/` deliberately small. It should not become a dumping ground for business logic that has no clear owner.

## 5. Hour 4 acceptance checklist

- [ ] Every planned Django app has a clear purpose and data owner.
- [ ] Event, opportunity and application ownership is explicit.
- [ ] Cross-domain writes go through owning services, with domain events for side effects.
- [ ] Important events use an outbox and idempotent consumers where appropriate.
- [ ] Authorization and trust-and-safety checks occur server-side at execution time.
- [ ] AI agents use typed, allowlisted capabilities rather than direct database access.
- [ ] Consequential AI actions have explicit approval rules and audit trails.
- [ ] Module dependencies avoid circular imports and private cross-domain access.
- [ ] The document is saved as `docs/domain-design.md` and committed to version control.

## Decisions intentionally deferred

- Exact database schema and indexes.
- Whether messaging needs group conversations, read receipts, typing indicators, presence, attachments or end-to-end encryption at launch.
- The specific agent framework/model provider and any external vector database.
- Extraction of any domain into a separate service. Do this only when measured operational or scaling needs justify it.

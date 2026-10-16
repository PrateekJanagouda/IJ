# ADR-001: Adopt a Modular Monolith for EQora

- **Status:** Accepted as the initial architecture direction
- **Date:** 2026-10-14
- **Decision owners:** EQora product and engineering
- **Related documents:** `docs/architecture.md`, `docs/domain-design.md`, `docs/api-and-security.md`, `docs/database-design.md`

## Context

EQora combines a professional/social network for artists with a gig and opportunity marketplace. The planned launch includes identity and profiles, posts, follows, likes, comments, shares, notifications, direct messaging, events, independently apply-able opportunities, applications, performer selection, and moderation. AI-assisted workflows may be introduced through controlled backend capabilities.

The product needs transactional consistency for applications and selections, common authentication and authorization, fast iteration, and a codebase that can be maintained without a large platform team. Splitting into microservices at the start would add network boundaries, distributed tracing and failure modes, deployment complexity, and cross-service consistency concerns before independent scaling requirements are known.

## Decision

Adopt a **modular monolith** for the initial implementation:
- One primary Django backend codebase using Django REST Framework.
- Domain-oriented Django apps with explicit data ownership and service interfaces.
- PostgreSQL as the authoritative store for durable product data.
- Redis for caching, rate limiting, and appropriate ephemeral coordination.
- Next.js/React/TypeScript for the web frontend.
- Background workers for slow/retriable tasks such as notification delivery and media processing.
- Django Channels/WebSockets for real-time messaging when implemented.
- Object storage for user-uploaded media.
- AI agents access approved, typed backend capabilities rather than direct database access.

The initial domain apps are identity, authorization, profiles, social, opportunities, messaging, notifications, trust and safety, media, audit, and AI orchestration. The team may combine or defer an app if the implementation remains clearly modular and ownership remains explicit.

## Decision drivers

1. Fast delivery and low operational overhead.
2. Consistent identity, authorization, and audit controls.
3. Atomic application and performer-selection workflows.
4. Full social and messaging functionality in the launch scope.
5. Clear internal boundaries and testability.
6. Ability to extract a module later based on measured needs.
7. Safe integration of AI tools without privileged model access.

## Consequences

### Positive

- One main application deployment and one primary relational database simplify initial operations.
- Domain services can use database transactions for workflows that span related entities.
- Shared authentication, authorization, validation, and audit conventions are easier to enforce.
- Developers can refactor internal boundaries without coordinating multiple service deployments.
- Modules can be independently tested and can later be extracted when justified.

### Negative and trade-offs

- A defect or resource-heavy operation can affect the whole backend deployment.
- Teams must enforce module boundaries through code review, tests, and dependency rules.
- Scaling a single hot domain independently is less straightforward than with a separate service.
- A shared database can tempt developers to bypass domain services unless ownership rules are enforced.

## Guardrails

- Each domain owns its tables and business rules.
- Cross-domain writes use explicit service interfaces; do not mutate another app's models directly.
- Use domain events and a transactional outbox for important asynchronous side effects.
- Enforce object-level authorization at backend entry points.
- Do not give AI agents direct database credentials or unrestricted tools.
- Add observability, migrations, backups, and automated tests from the beginning.
- Do not extract services based on speculative future scale alone.

## Reconsider this decision when

Revisit the architecture if one or more of the following becomes a measured, sustained constraint:
- A domain needs a substantially different scaling or availability profile.
- Independent deployment is necessary because team ownership or release cadence diverges.
- A workload's resource use materially degrades unrelated domains.
- Isolation requirements or regulatory boundaries require a separate service/data store.
- Operational evidence shows that extraction costs are justified by reliability or delivery benefits.

Any extraction should include ownership of data, API contracts, authorization, observability, failure handling, and migration/rollback plans.

## Alternatives considered

### Microservices from day one
Rejected for the initial phase because it increases operational and distributed-systems complexity before independent scaling or ownership needs are established.

### Unstructured monolith
Rejected because implicit dependencies and unclear data ownership would make social, messaging, marketplace, and AI capabilities harder to evolve safely.

### Serverless functions as the primary backend
Not selected as the main architecture because EQora's transactional domain workflows and real-time messaging benefit from a cohesive domain layer. Serverless components may still be used for appropriate integrations or asynchronous workloads.

## Validation

The decision is validated when:
- The backend has documented domain apps and ownership.
- Cross-domain operations go through defined interfaces.
- API and authorization tests cover critical boundaries.
- Database migrations and backup/restore are controlled.
- Deployment and monitoring are documented.

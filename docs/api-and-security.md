# EQora API and Security Baseline

**Milestone:** Hour 5  
**Status:** Proposed baseline for implementation  
**Architecture:** Next.js + TypeScript, Django REST Framework, PostgreSQL, Redis, modular monolith

## 1. Purpose

This document establishes consistent API conventions, a preliminary authentication strategy, and minimum security and privacy requirements for EQora. These requirements apply to the social network, artist profiles, events, opportunities, applications, direct messaging, notifications, moderation, and future AI-agent capabilities.

## 2. API conventions

### 2.1 Versioning and format

- Base path: `/api/v1/`
- Use REST-style resources and JSON encoded as UTF-8.
- Use plural, lowercase resource names.
- Use ISO 8601 timestamps in UTC.
- Use `PATCH` for partial updates.
- Use `DELETE` only where deletion semantics are explicit and safe.
- Use explicit command/action endpoints for consequential state transitions.
- Keep changes backward-compatible within v1. Introduce a new API version only for breaking contract changes.
- Do not put credentials, session identifiers, or sensitive data in URLs.

Examples:

```http
GET    /api/v1/profiles/{profile_id}/
GET    /api/v1/opportunities/?genre=indie&cursor=...
POST   /api/v1/opportunities/{opportunity_id}/applications/
GET    /api/v1/conversations/
POST   /api/v1/conversations/{conversation_id}/messages/
GET    /api/v1/notifications/?unread=true
POST   /api/v1/applications/{application_id}/accept/
```

The final route structure should be reviewed alongside the domain model and OpenAPI schema before implementation.

### 2.2 HTTP status codes

| Status | Meaning |
|---|---|
| `200 OK` | Request succeeded and returns a response |
| `201 Created` | Resource created |
| `202 Accepted` | Background operation accepted but not completed |
| `204 No Content` | Request succeeded without a response body |
| `400 Bad Request` | Malformed request or general validation failure |
| `401 Unauthorized` | Authentication missing or invalid |
| `403 Forbidden` | Authenticated caller lacks permission |
| `404 Not Found` | Resource absent or intentionally concealed |
| `409 Conflict` | Operation conflicts with current resource state |
| `413 Content Too Large` | Request or upload exceeds configured limit |
| `415 Unsupported Media Type` | Unsupported request content type |
| `422 Unprocessable Content` | Optional convention for semantically invalid content; use consistently if adopted |
| `429 Too Many Requests` | Rate limit exceeded |
| `500 Internal Server Error` | Unexpected server-side failure |

Use `400` for invalid input and `409` for state conflicts, such as attempting to apply to a closed opportunity. Use `404` where revealing the existence of a private resource would create a privacy risk. Do not use status codes inconsistently across endpoints.

### 2.3 Standard error envelope

Use a consistent error structure:

```json
{
  "error": {
    "code": "application_not_open",
    "message": "This opportunity is no longer accepting applications.",
    "details": {},
    "request_id": "req_example"
  }
}
```

Rules:
- `code` is a stable, machine-readable identifier.
- `message` is safe for display or mapping to a localized frontend message.
- `details` may contain field-level validation errors, but must not contain secrets or unnecessary personal data.
- `request_id` correlates the response with server logs and traces. It is not an authentication token.
- Never return stack traces, SQL errors, filesystem paths, secret values, internal prompts, or debugging dumps in production responses.

### 2.4 Validation and business rules

- Validate request shape, field types, lengths, formats, allowed values, and file sizes.
- Normalize data consistently where appropriate, such as email addresses and searchable text.
- Reject unexpected fields on sensitive write operations where practical.
- Treat all client-supplied identifiers and role claims as untrusted.
- Validate authorization and domain rules in backend services, not only in frontend code or serializers.
- Enforce critical invariants in PostgreSQL using foreign keys, unique constraints, check constraints, and transactions.
- Use atomic transactions for state transitions such as application acceptance and performer selection.
- Make retriable write operations idempotent where duplicate execution could create harm or duplicate side effects.
- Return field-specific errors without echoing sensitive submitted values.

### 2.5 Pagination, filtering, sorting

- Use cursor pagination for feeds, messages, and large or frequently changing collections.
- Use bounded page sizes with a server-defined maximum.
- Allowlist filter and sort fields. Never interpolate arbitrary client-provided SQL identifiers into queries.
- Define stable ordering, including a tie-breaker such as an immutable ID.
- Apply authorization and visibility filters before returning paginated results.
- Avoid exposing counts or metadata that leak private information.

### 2.6 OpenAPI and testing

Use Django REST Framework with an OpenAPI schema generated from the implemented API. Each endpoint should document:
- Purpose and HTTP method.
- Authentication and permission requirements.
- Path, query, and body parameters.
- Success and error response schemas.
- Pagination and filtering behavior.
- Side effects and relevant rate limits.

Review schema changes in code review. Keep interactive API documentation in development or behind appropriate access controls in production.

Test successful requests, invalid input, unauthenticated requests, cross-user access, role boundaries, rate limits, and conflicting state transitions. Explicitly test that users cannot read other users' private messages or modify opportunities they do not control.

## 3. Preliminary authentication strategy

### 3.1 Decision

For the initial browser-first product, use **server-managed Django sessions with secure cookies**, rather than storing long-lived bearer tokens in browser local storage.

This is a preliminary choice. If native mobile apps or third-party clients become launch requirements, define a separate token-based authentication design with rotation, revocation, expiry, and client-specific threat analysis.

### 3.2 Session requirements

- Use HTTPS in all production environments.
- Set session cookies `Secure`, `HttpOnly`, and an appropriate `SameSite` policy.
- Use Django's CSRF protection for state-changing browser requests authenticated by cookies.
- Never put session IDs in URLs or local storage.
- Rotate the session after login and privilege changes; invalidate it on logout.
- Set idle and absolute session lifetimes based on risk and product needs.
- Revoke sessions when accounts are disabled or a security incident requires it.
- Apply rate limits to login, registration, password reset, verification, and other abuse-prone flows.
- Use generic password-reset responses to reduce account enumeration.
- Store passwords only using Django's approved password hashing mechanisms. Never log or email passwords.
- Require stronger authentication or step-up verification for future high-risk administrative actions.

### 3.3 Authorization

- Deny access by default.
- Check authorization on every request and every resource operation.
- Distinguish platform roles from resource ownership and membership.
- Do not trust frontend role checks as enforcement.
- A user may hold more than one role, but role possession alone does not grant access to every resource.
- Organizers may manage only events and opportunities they own or are explicitly authorized to manage.
- Conversation access requires verified conversation membership and compliance with block and moderation rules.
- Moderation and administrative access must be narrowly scoped and audited.
- AI agents inherit a constrained actor context and must not bypass the same checks.

### 3.4 WebSockets

For Django Channels/WebSockets:
- Authenticate the connection using the same session where appropriate.
- Validate the origin and use secure WebSocket connections in production.
- Authorize conversation membership for every connection and relevant message action.
- Recheck permissions where needed after membership, account, or block state changes.
- Apply message size limits, connection limits, and rate limits.
- Do not treat possession of a conversation ID as authorization.

## 4. Security baseline

### 4.1 Application and infrastructure security

- Keep secrets outside source control. Use environment-specific secret management in deployment.
- Maintain separate development, staging, and production configurations.
- Set Django production settings securely, including `DEBUG=False`, allowed hosts, secure cookies, and HTTPS-related settings.
- Enforce TLS for client traffic and encrypted connections to managed services where available.
- Apply least privilege to database users, storage credentials, background workers, and deployment identities.
- Validate uploaded file type and size; do not trust the extension or browser MIME type alone.
- Store uploads in object storage, not as unbounded files on the application server.
- Keep dependencies patched and run dependency and secret scanning in CI.
- Run database migrations through a controlled deployment process.
- Back up PostgreSQL, encrypt backups, restrict access, and periodically test restoration.
- Define health checks, structured logs, error monitoring, and alerting without leaking sensitive data.
- Use security headers and a Content Security Policy appropriate to the frontend.
- Protect against CSRF, XSS, SQL injection, SSRF, insecure direct object references, and mass assignment.
- Use Django ORM parameterization; do not construct SQL by concatenating untrusted input.

### 4.2 Rate limiting and abuse prevention

Apply endpoint-appropriate limits to:
- Login, signup, password reset, and verification.
- Posting, commenting, following, liking, and sharing.
- Message sending and conversation creation.
- Opportunity applications and organizer actions.
- Search, media uploads, and AI tool execution.

Use Redis for distributed rate-limit state if required, but design limits so a Redis outage does not silently disable critical protections. Add spam detection and abuse review workflows as the product matures.

### 4.3 Auditability

Record security-sensitive and consequential events, including:
- Login and account security events.
- Role and permission changes.
- Event publication and cancellation.
- Application acceptance, rejection, and withdrawal.
- Moderation actions.
- AI tool executions, approvals, and outcomes.
- Administrative access to sensitive records.

Audit records should include actor, action, resource reference, timestamp, outcome, and correlation/request ID where applicable. Avoid logging passwords, session cookies, authentication tokens, full private message bodies, or unnecessary personal data. Restrict access to audit logs and define retention.

## 5. Privacy baseline

### 5.1 Data minimization and visibility

- Collect only information required for product functionality, safety, or clearly disclosed purposes.
- Define visibility rules for each profile field and content type.
- Treat private messages, account recovery data, authentication records, and moderation reports as sensitive.
- Enforce visibility server-side for feeds, search, profile pages, APIs, and AI tools.
- Avoid returning private fields merely because the caller can access the containing object.
- Provide clear controls for profile visibility, notification preferences, blocking, and reporting.
- Do not expose private account details in public URLs or search results.

### 5.2 Messaging and social content

- Only conversation participants and explicitly authorized processes may access message content.
- Block rules must be enforced for relevant interactions, including messaging and discovery, according to documented product behavior.
- Do not put message bodies or private profile details in routine application logs.
- Define what happens to posts, comments, messages, and portfolio media when an account is disabled or deleted.
- Explain to users what data moderation staff may access and under what conditions.
- Do not claim end-to-end encryption unless it is actually implemented and independently reviewed.

### 5.3 Retention, deletion, and user rights

Before public launch, document:
- What data is collected and why.
- Retention periods for accounts, messages, reports, audit records, and uploaded media.
- Account export and deletion processes.
- Treatment of records that must be retained for safety, fraud prevention, legal obligations, or dispute resolution.
- Backup expiration and deletion propagation.
- Procedures for handling privacy requests and incidents.

Retention periods must be chosen based on actual product needs and applicable law rather than left indefinite by default.

### 5.4 AI-specific privacy rules

- Provide agents only the minimum context required for a task.
- Do not send private data to external model providers unless the provider, configuration, user disclosure, and lawful basis have been reviewed.
- Treat posts, messages, profile text, uploads, and retrieved documents as untrusted input, not instructions that can override tool policy.
- Keep tool allowlists and authorization outside the model's control.
- Avoid training or fine-tuning on private user content without an explicitly approved policy and appropriate consent/legal basis.
- Log tool metadata and outcomes while minimizing retention of raw prompts and private content.
- Provide human review for consequential moderation and other high-impact decisions.
- Prevent an agent from acting on stale permissions or stale resource state; revalidate before writes.

## 6. Security incident readiness

Before launch:
- Define a channel for reporting security vulnerabilities.
- Establish an incident response owner and escalation procedure.
- Prepare credential rotation and session-revocation procedures.
- Monitor unusual login, messaging, scraping, and AI-tool activity.
- Test backup restoration and recovery procedures.
- Document how to investigate, contain, remediate, and communicate a privacy or security incident.

## 7. Implementation checklist

- [ ] Configure `/api/v1/` routing and consistent response conventions.
- [ ] Implement the standard error envelope and stable error codes.
- [ ] Generate and review the OpenAPI schema.
- [ ] Configure secure Django sessions and CSRF protection.
- [ ] Add object-level authorization tests for all sensitive domains.
- [ ] Configure production HTTPS, secure cookies, secret management, and safe Django settings.
- [ ] Add input validation, upload limits, and endpoint-specific rate limits.
- [ ] Add audit events for consequential operations.
- [ ] Define privacy visibility rules and account deletion/retention behavior.
- [ ] Add AI tool allowlists, actor-scoped authorization, approval gates, and execution auditing before enabling agents.
- [ ] Verify that logs and error responses do not leak secrets or private content.
- [ ] Test backup restoration and incident-response procedures.

## 8. Decisions to revisit before launch

1. Whether native mobile clients are part of the initial release.
2. Exact session lifetime and reauthentication policy.
3. Whether public API documentation is needed in production.
4. Retention periods and deletion exceptions for messages, reports, and audit records.
5. Whether any AI feature sends user content to an external model provider.
6. Whether high-risk accounts or administrative actions require multifactor authentication.
7. Applicable privacy, consumer, and platform obligations for EQora's launch jurisdictions.

## 9. Acceptance criteria

Hour 5 is complete when the team has agreed on the API contract, error conventions, session-based browser authentication, resource-level authorization, and the minimum security and privacy requirements above. These decisions should be reviewed during implementation and validated through automated tests and a pre-launch security review.

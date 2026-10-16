# EQora MVP Scope, User Journeys, and Permissions

**Document:** `docs/mvp-and-permissions.md`\
**Version:** 0.2\
**Status:** Confirmed MVP decisions, ready for domain and API design\
**Depends on:** `docs/product-requirements.md`

## 1. Purpose

This document defines EQora's first-release scope, three primary user
journeys, and role/permission model. Confirmed decisions:

1.  Full direct messaging ships at launch.
2.  Posts, likes, comments, shares, and notifications all ship at
    launch.
3.  An event may contain multiple independently apply-able performance
    slots, depending on host requirements. Standalone opportunities are
    also supported.

EQora is an integrated artist network and gig marketplace for the
live-performance ecosystem.

## 2. Prioritization

-   **P0: Required at launch.**
-   **P1: Early follow-up**, if not required by the pilot.
-   **P2: Future enhancement.**

### 2.1 P0: Required at launch

  --------------------------------------------------------------------------
  Area                    Feature                 Acceptance summary
  ----------------------- ----------------------- --------------------------
  Identity                Registration, login,    Users securely access
                          logout, account         their own accounts.
                          recovery                

  Roles                   Multiple roles per      One account can act as
                          account                 artist and organizer with
                                                  explicit permissions.

  Profiles                Artist, organizer,      Users edit only profiles
                          venue profiles          they own or are authorized
                                                  to manage.

  Portfolio               Skills, genres,         Organizers can assess
                          location, bio,          public-facing work.
                          experience, portfolio   
                          links/media references  

  Events                  Create and manage       Authorized hosts manage
                          events                  event resources.

  Opportunities and slots Standalone              One event can contain
                          opportunities and       multiple independently
                          event-associated        apply-able slots.
                          opportunities           

  Search                  Filters for type, date, Users discover relevant
                          location,               opportunities.
                          skills/genres,          
                          compensation where      
                          supplied                

  Applications            Apply, view own         State and access are
                          applications, review,   enforced server-side.
                          shortlist, accept,      
                          decline, withdraw       
                          subject to rules        

  Selection               Selected-performer list Organizers track
                          per opportunity/event   selections without complex
                                                  scheduling.

  Social graph            Follow/unfollow         Users build a network.

  Social feed             Create and view         Simple chronological or
                          permitted posts         explainable ordering.

  Engagement              Likes and comments      Basic social interaction
                                                  with ownership and
                                                  moderation rules.

  Sharing                 Shareable post/listing  Sharing never bypasses
                          URLs or in-product      access controls.
                          share action            

  Direct messaging        Conversation list,      Only participants can
                          history, send/receive,  access conversations.
                          unread state            

  Notifications           In-app notifications    Users see and manage their
                          for messages,           own notifications.
                          application changes,    
                          and social interactions 

  Trust and safety        Report profiles, posts, Users can report abuse;
                          comments, messages,     authorized moderators can
                          listings; basic         review.
                          moderation              

  Authorization           Server-side checks on   Users cannot access
                          protected               private data without
                          resources/actions       permission.

  Measurement             Funnel instrumentation  Measure listing →
                                                  application → selection →
                                                  confirmation/completion.
  --------------------------------------------------------------------------

### 2.2 P1: Early follow-up

-   Email and push notification delivery if the initial release uses
    in-app notifications.
-   Advanced availability calendars and scheduling.
-   Rich media upload/transcoding beyond the chosen initial storage
    approach.
-   Venue teams and multi-branch venue management.
-   Advanced search relevance and saved searches.
-   Expanded organizer analytics.

The three confirmed requirements above must not be silently downgraded.

### 2.3 P2: Future enhancements

-   Integrated ticketing, payments, refunds, payouts, and revenue
    splits.
-   Contracts, invoicing, escrow, and tax workflows.
-   Native mobile apps if responsive web validates the product first.
-   Livestreaming and built-in video hosting.
-   AI recommendations and autonomous agents.
-   Advanced ML feed ranking.
-   Automated lineup optimization.
-   Full CRM and analytics suites.
-   Advanced verification and reputation scoring.
-   Microservices without a demonstrated need.

## 3. Three main user journeys

### Journey A: Artist discovers and applies for an opportunity

**Goal:** An artist finds a relevant opportunity, applies, and tracks
the outcome.

1.  Artist registers/logs in.
2.  Artist creates a profile with skills, genres, location, experience,
    and portfolio links.
3.  Artist browses the feed or searches opportunities.
4.  Artist opens a specific opportunity/slot and reviews requirements,
    date/time, location, compensation terms where applicable, and
    deadline.
5.  Artist applies with an optional message and portfolio references.
6.  Server validates that the opportunity is open and the artist is
    eligible.
7.  Application is recorded as `submitted`.
8.  Artist views their own application and status.
9.  Authorized organizer moves it to `shortlisted`, `accepted`, or
    `declined`.
10. System records the change and notifies the artist.
11. Artist and organizer can discuss details through direct messaging.
12. If selected, booking and performance outcomes are tracked separately
    from application status.

**Alternate/error paths** - Closed or expired opportunities reject
applications. - Duplicate active applications are prevented according to
product rules. - Withdrawal is allowed only under configured rules. -
Unauthorized organizers cannot view private applications or change
statuses. - Cancellation notifies affected applicants. - Reports about
suspicious listings go to moderation without exposing the reporter to
the reported party.

**Success condition:** Artist can apply and reliably see status without
accessing other applicants' private data.

### Journey B: Organizer publishes an event/opportunity and selects performers

**Goal:** Organizer publishes an event or standalone opportunity,
reviews applications, and selects performers.

1.  Organizer registers/logs in and creates an organizer profile.
2.  Organizer creates an event, a standalone opportunity, or opens an
    event they are authorized to manage.
3.  If the event needs multiple performers, organizer creates
    independently apply-able opportunities/slots under it.
4.  Organizer defines title, description, type, date/time or slot
    window, location, eligibility, skills/genres, compensation where
    applicable, and deadline.
5.  Server validates the listing before publication.
6.  Artists discover and apply to individual opportunities/slots.
7.  Organizer views applications only for opportunities they own or
    manage.
8.  Organizer reviews portfolios and shortlists, accepts, or declines
    applicants.
9.  System validates and records each change and notifies affected
    artists.
10. Organizer maintains a selected-performer list/basic lineup.
11. Organizer communicates with applicants through direct messaging.
12. Organizer updates event/opportunity states and records confirmation,
    completion, or cancellation when appropriate.

**Alternate/error paths** - Incomplete listings cannot be published. -
Hosts cannot review another host's private applications. -
Closed/cancelled/expired opportunities cannot accept applications. -
Only owners or assigned managers can edit/cancel. - Cancelling an event
with accepted performers requires confirmation and notifications. -
Standalone opportunities do not require an event. - Event-associated
slots must reference a valid parent event.

**Success condition:** Organizer can publish listings, review
applications, communicate, and select performers without spreadsheets
for the core workflow.

### Journey C: User discovers and engages with artists and events

**Goal:** User discovers creative work, builds a network, and finds
opportunities.

1.  User registers/logs in.
2.  User views permitted public profiles, posts, events, and
    opportunities.
3.  User follows artists, organizers, or venues.
4.  User creates posts or likes, comments on, or shares posts.
5.  User visits a profile, event, or opportunity from content.
6.  User discovers an opportunity and takes the next action.
7.  User starts or continues a direct message where messaging rules
    allow it.
8.  System creates in-app notifications for relevant likes, comments,
    messages, and application changes.
9.  User can report abusive or misleading content.

**Alternate/error paths** - Users edit/delete only their own posts,
subject to policy. - Shareable URLs never grant access to private
content. - Users access only conversations in which they participate. -
Deleted/moderated content is not shown as ordinary public content. -
Rate limits, blocking/reporting, and moderation help reduce abuse.

**Success condition:** Users discover and engage with creators and
opportunities while privacy and ownership rules remain enforceable.

## 4. Event and opportunity domain rule

**An event and an opportunity are separate concepts.**

-   **Event:** The overall happening, such as an open mic, festival,
    concert, audition day, or jam session. It contains general event
    information such as name, host, venue, date, description, and public
    status.
-   **Opportunity:** A specific role, performance slot, audition, or gig
    for which an artist can apply. It contains requirements,
    compensation, deadline, status, and selection workflow.
-   **Event-associated opportunity:** An opportunity linked to an event.
    One event can have zero, one, or many opportunities.
-   **Standalone opportunity:** A gig or audition that does not require
    a parent event.

Examples: - An open mic can have eight singer slots, each with its own
application and selection state. - A festival can have separate
opportunities for bands, DJs, dancers, and hosts. - A paid private gig
can exist as a standalone opportunity. - An audition can be standalone
or a slot within an audition event.

**Modeling implications** - Applications attach to an opportunity, not
the event as a whole. - Event-level information and opportunity-level
requirements remain distinct. - Each opportunity has its own deadline,
eligibility, application status, and selected performers. - Cancellation
propagation and notifications must be defined. - Do not assume every
event needs a slot or every opportunity needs a parent event.

## 5. Roles and permission model

### 5.1 Principle: role is not ownership

Roles describe general capabilities, not universal access to resources.
Artists edit their own profiles; organizers manage only owned or
assigned opportunities; venue managers need explicit assignments. One
account may hold multiple roles. Moderation permissions are separate.

Use role-based access control (RBAC) plus resource-level authorization.
Hiding a frontend button is not a security boundary.

### 5.2 Roles

  -----------------------------------------------------------------------
  Role                                Description
  ----------------------------------- -----------------------------------
  Visitor                             Unauthenticated; can view only
                                      explicitly public content.

  Registered user                     Authenticated account with basic
                                      social capabilities and settings.

  Artist                              Maintains a performer profile and
                                      can apply for opportunities.

  Organizer                           Creates/manages owned or assigned
                                      events/opportunities and reviews
                                      applications.

  Venue manager                       Explicitly assigned to manage venue
                                      profiles and relevant listings.

  Moderator                           Reviews reports and performs
                                      defined moderation actions.

  Administrator                       Authorized operational,
                                      configuration, and moderation
                                      privileges.
  -----------------------------------------------------------------------

An account may be both Artist and Organizer. Venue permissions are
explicitly assigned, not inferred from a profile name or email address.

### 5.3 Permission matrix

Legend: **Own** = owned resources; **Assigned** = explicitly assigned
resources; **Public** = published public content; **Limited** = minimum
necessary access; **No** = not allowed by default.

  --------------------------------------------------------------------------------------------------------------------------------------------------------
  Action/resource                       Visitor   Registered user  Artist                 Organizer       Venue manager   Moderator       Administrator
  ------------------------------------- --------- ---------------- ---------------------- --------------- --------------- --------------- ----------------
  View public                           Public    Public           Public                 Public          Public          Public          Public
  profiles/posts/events/opportunities                                                                                                     

  Edit own account settings             No        Own              Own                    Own             Own             Own             Own

  Create/edit artist profile            No        Own if enabled   Own                    Own if also     Own if also     Own             Own
                                                                                          artist          artist                          

  Create/edit organizer profile         No        Own if enabled   Own if also organizer  Own             Own if also     Own             Own
                                                                                                          organizer                       

  Create/edit venue profile             No        No by default    No by default          If assigned     Assigned        No by default   Audited override

  Create/edit own post                  No        Own              Own                    Own             Own             Own; moderation Own; moderation
                                                                                                                          separate        separate

  Like/comment/share public content     No        Yes, subject to  Yes                    Yes             Yes             Yes             Yes
                                                  policy                                                                                  

  Follow/unfollow accounts              No        Yes              Yes                    Yes             Yes             Yes             Yes

  Create/publish event                  No        No by default    If                     Own/assigned    If assigned     No by default   Audited override
                                                                   organizer-authorized                                                   

  Create/publish opportunity/slot       No        No by default    If                     Own/assigned    If assigned     No by default   Audited override
                                                                   organizer-authorized                                                   

  Edit/close/cancel event               No        No               No unless assigned     Own/assigned    Assigned        Moderation      Audited override
                                                                                                                          restriction     
                                                                                                                          only            

  Edit/close/cancel opportunity         No        No               No unless assigned     Own/assigned    Assigned        Moderation      Audited override
                                                                                                                          restriction     
                                                                                                                          only            

  Apply to opportunity                  No        Only with artist Yes                    Only if also    Only if also    Only if also    Only if also
                                                  capability                              artist          artist          artist          artist

  View own applications                 No        Own if applicant Own                    Own if also     Own if also     Own if also     Own if also
                                                                                          artist          artist          artist          artist

  View applications for opportunity     No        No               Own application only   Own/assigned    Assigned        Limited         Audited access
                                                                                                                          investigation   
                                                                                                                          access          

  Shortlist/accept/decline              No        No               No                     Own/assigned    Assigned if     No by default   Audited override
                                                                                                          delegated                       

  Send direct message                   No        Yes, subject to  Yes                    Yes             Yes             Only under      Only under
                                                  safety/privacy                                                          policy          policy

  Read private conversations            No        Participant      Participant            Participant     Participant     Limited,        Limited, audited
                                                  conversations    conversations only     conversations   conversations   audited         access
                                                  only                                    only            only            investigation   

  View/mark own notifications           No        Own              Own                    Own             Own             Own             Own

  Report user/content/listing/message   No by     Yes              Yes                    Yes             Yes             Yes             Yes
                                        default                                                                                           

  Review reports                        No        No               No                     No              No              Assigned        As operationally
                                                                                                                          reports         required

  Hide/remove content through           No        No               No                     No              No              Within assigned Within policy
  moderation                                                                                                              scope           

  Suspend/disable account               No        No               No                     No              No              Only if         Yes, audited
                                                                                                                          explicitly      
                                                                                                                          granted         

  Change system configuration           No        No               No                     No              No              No              Authorized
                                                                                                                                          administrators
                                                                                                                                          only
  --------------------------------------------------------------------------------------------------------------------------------------------------------

The matrix describes intended capabilities. Implement only the
permissions required for launch and make exceptions explicit.

### 5.4 Resource-level rules

1.  Users edit only profiles they own or are authorized to manage.
2.  Post owners can edit/delete their own content; moderator actions are
    separate and audited.
3.  Event owners or assigned managers can edit, publish, or cancel
    events.
4.  Opportunity owners or assigned managers can edit, publish, close, or
    cancel opportunities.
5.  Applicants can view their own applications; organizers can view
    applications only for opportunities they manage.
6.  Only authorized opportunity managers can change application status.
7.  Users access only conversations in which they participate, except
    narrowly controlled, audited investigation access.
8.  Users can read/update only their own notifications.
9.  Venue access is explicitly assigned.
10. Administrative actions require explicit permissions and audit
    logging.
11. Sharing never bypasses access control.
12. Cancelling an event with accepted performers requires a deliberate
    workflow and notifications.

### 5.5 Suggested application states

Initial statuses: `submitted`, `shortlisted`, `accepted`, `declined`,
`withdrawn`.

-   New valid applications enter `submitted`.
-   An authorized organizer may move `submitted` to `shortlisted`,
    `accepted`, or `declined`.
-   An authorized organizer may move `shortlisted` to `accepted` or
    `declined`.
-   Artists may withdraw their own applications while permitted.
-   Final states must not be silently overwritten. Record actor,
    timestamp, prior state, new state, and reason where appropriate.
-   Booking/performance outcomes are separate, e.g. `confirmed`,
    `completed`, or `cancelled`.
-   Every application belongs to one opportunity, which may or may not
    belong to an event.

## 6. Direct messaging requirements

Full direct messaging is required at launch:

-   Conversation list for the current user.
-   One-to-one conversations at minimum.
-   Persistent message history with sender and timestamp.
-   Sending and receiving messages.
-   Unread state or unread counts.
-   In-app notifications for new messages.
-   Authorization so only participants can read/send messages.
-   Rate limits and controls for blocking/reporting users.
-   Basic abuse-report workflow.
-   Safe handling of deleted or suspended accounts.

Group chats, read receipts, typing indicators, online presence,
attachments, voice messages, and end-to-end encryption are not
automatically included; decide these separately. WebSockets may support
real-time delivery, but persistence and authorization must work
independently of transport.

## 7. Social and notification requirements

All of the following ship at launch:

-   Posts and feed.
-   Likes, with duplicate likes prevented.
-   Comments, with ownership and moderation rules.
-   Shareable post/listing URLs or an in-product share action.
-   Follow/unfollow.
-   In-app notifications for relevant likes, comments, follows where
    appropriate, messages, and application status changes.
-   Read/unread state for notifications.
-   Pagination and basic spam/rate controls.

The feed may use chronological or simple deterministic ordering.
Advanced ML ranking is not required. Notifications are derived signals,
not the source of truth: the application record remains authoritative
for application status.

## 8. Authorization implementation guidance

-   Enforce authorization in backend service/API layers for every
    protected read/write.
-   Use ownership and explicit assignments, not role labels alone.
-   Deny by default for sensitive actions.
-   Validate resource state, such as whether an opportunity is open.
-   Do not expose private applicant data in public listing responses.
-   Apply rate limits to login, applications, comments, messaging, and
    reports.
-   Audit moderation, administrative overrides, and consequential
    application/booking changes.
-   Test allowed and denied paths, including cross-user access attempts.
-   Keep frontend visibility aligned with backend permissions while
    treating the backend as authoritative.

## 9. MVP acceptance checklist

### Product workflow

-   [ ] Artist can create a profile and portfolio.
-   [ ] Host can publish an event and create multiple independently
    apply-able opportunities/slots under it.
-   [ ] Host can publish a standalone opportunity without an event.
-   [ ] Artist can discover and apply to an open opportunity.
-   [ ] Artist can view their own application status.
-   [ ] Authorized organizer can review/update applications.
-   [ ] Selected performers can be tracked against the relevant
    opportunity/event.
-   [ ] Users can follow accounts and discover public profiles/listings.
-   [ ] Users can create posts, like, comment, and share.
-   [ ] Users can send/receive direct messages and see their own
    conversations.
-   [ ] Relevant social, messaging, and application events create in-app
    notifications.
-   [ ] Users can report suspicious or abusive content.

### Authorization and safety

-   [ ] Artist cannot view another artist's private applications.
-   [ ] Organizer cannot view or modify applications for an opportunity
    they do not manage.
-   [ ] Unauthorized users cannot edit/cancel another user's event or
    opportunity.
-   [ ] Users cannot read another user's private messages or
    notifications.
-   [ ] Moderation actions are restricted and recorded.
-   [ ] Invalid or stale application transitions are rejected.
-   [ ] Shareable URLs do not bypass privacy rules.
-   [ ] Automated tests cover positive and negative authorization cases.

### Pilot measurement

-   [ ] Listing publication, application, selection, booking
    confirmation, and performance completion are measurable.
-   [ ] Confirmed bookings are distinguishable from completed
    performances.
-   [ ] Feedback can be collected from artists and organizers.

## 10. Decisions still open

-   Initial pilot geography and target creative community.
-   Whether all performer categories launch equally or a smaller segment
    is prioritized.
-   Whether direct messaging supports attachments, group chats, read
    receipts, and typing indicators.
-   Whether any user can initiate a message or whether privacy settings,
    follows, or mutual consent constrain initiation.
-   Blocking behavior and visibility of public content to blocked users.
-   Whether public users can view content without an account.
-   Exact event/opportunity fields and time-zone handling.
-   Whether selection is stored against an opportunity, an event, or
    both. Recommended source of truth: selection against the
    opportunity, with event-level lineup aggregation.
-   Cancellation rules after performers are accepted.
-   Public profile and portfolio visibility defaults.
-   Media limits, storage, moderation, retention, and deletion.
-   Monetization model and whether it affects the first release.

## Definition of done for Hour 2

Hour 2 is complete when the team agrees on the MVP boundary, reviews the
three user journeys, accepts role and resource-ownership principles, and
records unresolved policy choices.

**Confirmed launch decisions:** full direct messaging; posts, likes,
comments, shares, and notifications; and events containing multiple
independently apply-able opportunities/slots, as well as standalone
opportunities.

These decisions inform the domain model, database relationships, API
contracts, and authorization tests.

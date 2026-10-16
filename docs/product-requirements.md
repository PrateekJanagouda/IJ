# EQora Product Requirements

**Document:** `docs/product-requirements.md`\
**Version:** 0.1\
**Status:** Initial product definition\
**Purpose:** Define EQora's product vision, users, MVP scope,
assumptions, and validation criteria before implementation.

------------------------------------------------------------------------

## 1. Product summary

**EQora is an integrated artist network and gig marketplace for the
live-performance ecosystem.** It helps artists build a professional
presence, discover and apply for performance opportunities, connect with
other creatives, and grow an audience. It helps event organizers and
venues discover talent, manage applications, and assemble lineups.

EQora combines three connected experiences:

1.  **Professional identity:** artist, organizer, and venue profiles
    that communicate who users are and what they do.
2.  **Social discovery:** a feed and social interactions that help users
    discover artists, venues, events, and creative work.
3.  **Opportunity management:** listings and application workflows that
    help artists move from discovering an opportunity to being
    considered and selected for a performance.

The product's central promise is to help people in the live-performance
ecosystem find each other and turn those connections into real
opportunities.

## 2. Problem statement

Artists and performers often rely on scattered social-media posts,
informal communities, word of mouth, and individual messages to find
open mics, paid gigs, auditions, and other performance opportunities.
Their work and professional information may be spread across multiple
platforms, making it difficult to present a consistent portfolio,
identify relevant opportunities, and track applications.

Event organizers and venues face the reverse problem. They may have
difficulty discovering suitable performers, comparing portfolios,
collecting applications, communicating with applicants, and assembling a
lineup without a manual, fragmented process.

Collaborators and audiences also have limited ways to discover emerging
talent and follow the creative work and events they care about in one
place.

**Problem to solve:** There is no single, focused workflow in the
intended product experience that connects creative identity, community
discovery, and performance-opportunity management from first discovery
through application and selection.

This is the product hypothesis EQora must validate with real artists,
organizers, and venues. It should not be treated as proven market
research.

## 3. Product vision

> **Every artist deserves a stage. Every stage deserves its artists.**

EQora aims to become a trusted professional and social network for the
live-performance ecosystem, where artists can showcase their work,
discover opportunities, build relationships, and grow their careers,
while organizers and venues can discover talent and coordinate
performances.

### Product principles

-   **Opportunity first:** Social activity should help users discover
    people, events, and opportunities, not become an end in itself.
-   **Useful profiles:** Profiles should make it easy to understand a
    person's skills, style, experience, location, and work.
-   **Two-sided value:** EQora must be useful to both talent and the
    people who create or fill performance opportunities.
-   **Clear status and expectations:** Opportunity listings should
    communicate requirements, dates, location, compensation where
    applicable, deadlines, and application status.
-   **Trust and safety by design:** Users need control over their
    profiles and communication, and must be able to report abuse, spam,
    scams, or misleading listings.
-   **Human-controlled decisions:** Organizers remain responsible for
    selecting performers. Automation may assist discovery and
    administration but should not silently make consequential decisions.
-   **Build for learning:** Start with a coherent MVP, measure real
    outcomes, and expand based on observed user needs.

## 4. Target users and needs

A single account may support multiple roles. Roles describe how a person
uses EQora; permissions must still be enforced for each resource and
action.

### 4.1 Artists and performers

Examples include singers, instrumentalists, bands, DJs, dancers,
comedians, spoken-word artists, hosts, and other live performers.

**Core needs** - Create a professional profile and portfolio. - Show
skills, genres, location, experience, availability, and relevant media
or external portfolio links. - Discover open mics, paid gigs, auditions,
and other performance opportunities. - Filter opportunities by relevant
attributes such as location, date, type, genre, compensation, and
application deadline. - Apply with a message and relevant portfolio
information. - Track applications and receive status updates. - Follow
artists, venues, organizers, and events; share work and interact with
posts. - Communicate with organizers and collaborators.

### 4.2 Event organizers

Examples include independent event producers, open-mic hosts, festival
teams, and organizations running live events.

**Core needs** - Create an organizer profile. - Publish, edit, close,
and manage opportunity listings. - Specify eligibility, required skills
or genres, event details, dates, location, compensation, application
deadline, and other expectations. - Discover artists and review their
profiles and portfolios. - Receive, compare, shortlist, accept, or
decline applications. - Contact applicants and manage a lineup or
selected-performer list. - Promote events and communicate updates.

### 4.3 Venues

Examples include cafes, bars, performance spaces, auditoriums, studios,
and other places hosting live performances.

**Core needs** - Create a venue profile with location, capacity or
facilities where relevant, media, and contact or enquiry details. -
Promote events and opportunities hosted at the venue. - Connect with
artists and organizers. - Make venue requirements and available
performance opportunities clear.

A venue may be represented by an authorized account or team. MVP
implementation should avoid assuming that every venue is owned by a
single individual.

### 4.4 Creative collaborators

Examples include musicians seeking bandmates, producers, photographers,
sound engineers, composers, and creative teams.

**Core needs** - Find collaborators by skill, location, interests, and
portfolio. - Showcase their work and interests. - Connect and
communicate with other creatives.

### 4.5 Audience and fans

**Core needs** - Discover artists, events, and local live-performance
activity. - Follow creators and venues. - Like, comment on, and share
public posts. - Save or otherwise keep track of interesting events if
that feature is included in the MVP. - Access clear event information
and relevant external booking or ticket links when available.

### 4.6 Administrators and moderators

**Core needs** - Review user reports and potentially harmful listings or
content. - Take proportionate moderation actions. - Investigate spam,
impersonation, harassment, scams, and policy violations. - Maintain
auditability for sensitive administrative actions.

## 5. Primary user journeys

### Journey A: An artist finds and applies for a performance

1.  The artist creates an account.
2.  The artist creates a profile with relevant skills, genres, location,
    bio, and portfolio.
3.  The artist discovers opportunities through search, filters, the
    feed, or an organizer profile.
4.  The artist reviews the requirements and applies before the deadline.
5.  The artist sees the application in their dashboard and receives
    status updates.
6.  The organizer reviews the application and may shortlist, accept, or
    decline it.
7.  The artist and organizer communicate about next steps.
8.  If selected, the artist and organizer can mark the booking or
    performance as confirmed and later record its outcome.

### Journey B: An organizer finds performers and builds a lineup

1.  The organizer creates an account and organizer profile.
2.  The organizer publishes an opportunity with complete requirements
    and deadlines.
3.  Artists discover and apply for the opportunity.
4.  The organizer reviews applications and artist portfolios.
5.  The organizer shortlists, accepts, or declines applicants.
6.  The organizer communicates with selected performers and maintains
    the selected-performer list or lineup.
7.  The organizer updates the opportunity and records whether the
    performance was completed or cancelled.

### Journey C: A user discovers artists and events socially

1.  A user completes a profile and chooses interests or follows relevant
    accounts.
2.  The user sees posts from followed accounts and content available for
    discovery.
3.  The user likes, comments on, or shares content.
4.  The user visits artist, venue, organizer, or event profiles.
5.  The user discovers an opportunity or event and takes a relevant next
    action.

## 6. MVP scope

The MVP should deliver a coherent end-to-end experience for discovering
opportunities and connecting artists with organizers, supported by core
social networking.

### 6.1 Identity and access

-   Registration, login, logout, and account recovery.
-   Basic account settings.
-   One account can act in multiple supported roles.
-   Profile and resource permissions enforced on the server.
-   Safe defaults for private or sensitive account data.

### 6.2 Profiles and portfolios

-   Artist, organizer, and venue profile types.
-   Basic profile fields appropriate to each type.
-   Artist skills, genres, location, experience, and portfolio links or
    media references.
-   Profile viewing and editing.
-   Follow or connect functionality where appropriate.
-   Validation and moderation controls for profile content.

### 6.3 Social feed and interactions

-   Create, edit, and delete one's own posts, subject to product rules.
-   Support text and links, with media upload or embedding limited to
    the chosen MVP storage approach.
-   Feed of followed accounts and/or recent public posts.
-   Likes and comments.
-   Sharing posts through an in-product share action or shareable URL.
-   Follow and unfollow.
-   Basic notifications for relevant interactions.
-   Pagination and basic abuse controls.

For the first release, a simple, explainable feed is sufficient.
Advanced machine-learning ranking is not required.

### 6.4 Events and performance opportunities

-   Create, edit, publish, close, and view event or opportunity
    listings.
-   Support open mics, paid gigs, auditions, and other performance
    opportunities.
-   Distinguish an **event** from an **opportunity** where necessary: an
    event is something people may attend; an opportunity is a role or
    slot for which a performer can apply. One event may contain multiple
    opportunities.
-   Include title, description, organizer, location or online status,
    date/time, opportunity type, eligibility or requirements,
    compensation terms where applicable, application deadline, and
    status.
-   Search and filter by location, date, opportunity type, genre or
    skill, and compensation where provided.
-   Show clear listing status and application deadlines.
-   Provide a report-listing action.

### 6.5 Applications and selection

-   Artists can submit an application to an open opportunity.
-   Applications may include a message and portfolio references.
-   Artists can view their own applications and current statuses.
-   Organizers can view applications to opportunities they manage.
-   Organizers can shortlist, accept, or decline applications.
-   Prevent duplicate active applications where product rules require
    it.
-   Validate that applications are open and eligible before accepting
    submissions.
-   Record important status changes and notify affected users.
-   Allow authorized organizers to maintain a selected-performer list or
    basic lineup.

Initial application statuses may include `submitted`, `shortlisted`,
`accepted`, `declined`, and `withdrawn`. Booking or performance status
should be tracked separately where needed, for example `confirmed`,
`completed`, or `cancelled`.

### 6.6 Messaging and notifications

-   Provide a basic, safe way for artists and organizers to communicate.
    This may be direct messaging or a simpler contact/enquiry flow if
    full messaging is too costly for the first pilot.
-   Notify users about application status changes and relevant social
    interactions.
-   Provide an in-app notification list and read/unread state.
-   Apply authorization, rate limiting, blocking/reporting controls, and
    privacy rules.
-   Email or push delivery can be added according to implementation
    priorities; the system should not promise a delivery channel until
    it is implemented.

### 6.7 Trust, safety, and administration

-   Report users, posts, comments, and opportunity listings.
-   Basic admin workflows to review reports and take action.
-   Rate limits and spam prevention for sensitive actions.
-   Server-side authorization checks for all protected operations.
-   Clear community guidelines and opportunity-listing expectations.
-   Audit important administrative and application status changes.

## 7. Explicit non-goals for the initial MVP

The following are not required to validate the first product hypothesis.
They may be considered after pilot feedback.

-   Full ticketing infrastructure, payment processing, refunds, or
    revenue splits.
-   Escrow, contracts, invoicing, payroll, or tax management.
-   Livestreaming or built-in video hosting.
-   Advanced AI agents that autonomously contact users, select
    performers, or change bookings.
-   Machine-learning recommendation or feed-ranking systems.
-   Automated lineup optimization and complex scheduling solvers.
-   Microservices architecture or event-driven infrastructure beyond
    what the MVP needs.
-   A complete CRM for venues or organizers.
-   Advanced analytics and monetization dashboards.
-   Guaranteed background checks or verification of every user and
    listing.
-   A native mobile application if a responsive web experience can
    validate the concept first.

These exclusions are sequencing decisions, not a statement that the
capabilities will never belong in EQora.

## 8. Assumptions to validate

The product definition currently rests on these assumptions:

1.  Artists experience enough friction finding relevant performance
    opportunities that a dedicated platform would be valuable.
2.  Organizers and venues are willing to publish opportunities and
    review applications through a shared platform.
3.  Both sides will maintain useful profiles if those profiles help them
    discover or secure opportunities.
4.  A combined social network and gig marketplace creates more value
    than a listings-only service because relationships and portfolios
    support discovery.
5.  Open mics, paid gigs, auditions, and other performance opportunities
    can share a common listing and application foundation while allowing
    type-specific details.
6.  Users will initially accept a simple application workflow before
    expecting integrated contracts or payments.
7.  A focused geographic or community pilot can generate enough supply
    and demand to test the workflow.
8.  Users will trust the platform more if listing details, selection
    statuses, reporting, and communication expectations are clear.

These assumptions are hypotheses, not established facts. Validate them
through interviews, prototype tests, and a small real-world pilot.

## 9. North-star metric and supporting metrics

### North-star metric

**Successful performance connections per month**

Count unique artist-to-organizer or artist-to-venue connections that
result in a confirmed booking or completed performance during a calendar
month. Define deduplication rules before analytics implementation so
that one booking is not counted multiple times across status changes.

Track confirmed bookings and completed performances separately.
Completed performances are the stronger outcome; confirmed bookings are
a useful leading indicator.

### Supporting metrics

  -----------------------------------------------------------------------
  Metric                              Definition or purpose
  ----------------------------------- -----------------------------------
  Artist activation rate              Share of new artist accounts that
                                      complete a usable profile and
                                      portfolio.

  Organizer activation rate           Share of new organizer accounts
                                      that publish a valid opportunity.

  Opportunity application rate        Share of opportunity detail views
                                      that lead to an application,
                                      interpreted with context.

  Application-to-selection rate       Share of submitted applications
                                      that are accepted or selected.

  Organizer response rate             Share of applications receiving a
                                      recorded organizer decision or
                                      meaningful status update.

  Time to first relevant opportunity  Time from artist activation to
                                      first application to a suitable
                                      listing.

  Time to first booking               Time from artist activation to
                                      first confirmed booking through
                                      EQora.

  Opportunity fill rate               Share of opportunities that reach
                                      the organizer's intended fill or
                                      lineup state.

  Repeat organizer rate               Share of organizers who publish
                                      another opportunity after their
                                      first listing.

  Trust and safety rate               Reports, substantiated issues, spam
                                      signals, and time to review,
                                      interpreted alongside usage volume.

  Social engagement                   Likes, comments, follows, and
                                      shares, used as supporting
                                      indicators rather than the primary
                                      measure of success.
  -----------------------------------------------------------------------

Avoid selecting numerical targets without baseline data. Establish
baseline measurements in the pilot, then set time-bound targets based on
observed funnel performance and user feedback.

## 10. MVP success criteria

The MVP is ready for a controlled pilot when:

1.  Artists can register, create a usable portfolio, and discover
    relevant opportunities.
2.  Organizers can publish opportunities with clear requirements, dates,
    locations, compensation details where applicable, and deadlines.
3.  Artists can submit applications and reliably see their status.
4.  Organizers can review applications, update statuses, communicate
    with applicants, and select performers.
5.  Relevant status changes generate visible notifications.
6.  Users can create posts, follow accounts, and use likes, comments,
    and sharing without accessing content or actions they are not
    authorized to access.
7.  Reporting and basic moderation workflows are available.
8.  Core user journeys are covered by automated tests, including
    authorization and invalid application states.
9.  The pilot can measure the opportunity funnel from listing
    publication through applications, selection, confirmation, and
    completion.
10. Real artists and organizers use the system, and pilot evidence shows
    whether it produces relevant applications and at least some
    confirmed performance connections.

### Pilot evaluation

Run a small pilot with a clearly defined community or geographic area.
Recruit both artists and organizers before judging marketplace
performance; a platform with many artists but no opportunities, or many
listings but few relevant artists, will not provide balanced value.

Collect: - Short interviews with artists and organizers. - Listing
quality and relevance feedback. - Application and organizer-response
funnel data. - Confirmed bookings and completed performances. - Reasons
for abandonment, rejection, cancellation, or low response. - Reports of
confusing, misleading, or unsafe experiences.

At the end of the pilot, decide whether to improve the current workflow,
narrow the target segment, or expand the product.

## 11. Product boundaries and operational principles

-   The backend is the authority for authentication, authorization,
    application status, and booking state.
-   Clients must not be trusted to enforce permissions or determine
    whether an application is valid.
-   Important status transitions should be validated and recorded.
-   Notifications are delivery mechanisms, not the source of truth for
    an application's state.
-   Feed ranking and recommendations must not override privacy settings
    or access controls.
-   AI-assisted features, if introduced later, must operate through
    authorized tools and validated backend workflows. Consequential
    actions such as accepting an artist, confirming a booking, or
    sending messages on a user's behalf should require explicit
    authorization and appropriate user control.
-   Media storage, moderation, retention, and deletion behavior must be
    defined before broad public launch.
-   Personal data collection should be limited to what is needed for
    product functionality, safety, and operations.

## 12. Decisions still open

The following decisions should be made during product discovery or
technical design, rather than silently assumed:

-   Initial pilot city, community, and launch segment.
-   Whether the first release supports all performer categories equally
    or prioritizes a smaller initial set.
-   Whether direct messaging is in the first pilot or begins as a
    contact/enquiry workflow.
-   Whether event attendance discovery and ticket links are sufficient
    initially, or integrated ticketing is required by the business
    model.
-   Whether artist availability, compensation ranges, and organizer
    verification are mandatory listing fields.
-   Media upload limits, storage provider, and moderation workflow.
-   Exact profile visibility and privacy defaults.
-   Whether venue accounts support teams and multiple authorized
    representatives.
-   The event/opportunity data model and how multiple performance slots
    relate to a single event.
-   Initial monetization approach. Do not make payment architecture a
    dependency until the business model requires it.

## 13. First release recommendation

Build the first release around the smallest complete loop:

**Artist profile → opportunity discovery → application → organizer
review → selection → confirmed performance connection.**

Support that loop with enough social functionality to make profiles
discoverable and relationships useful: follows, posts, likes, comments,
shares, and notifications.

Keep the feed simple, keep application state reliable, make listing
quality a priority, and measure real-world outcomes. Expand into
ticketing, payments, advanced recommendations, and AI workflows only
when user evidence justifies the additional complexity.

------------------------------------------------------------------------

**Definition of done for Hour 1:** The team agrees on the problem,
vision, initial users, primary journeys, MVP boundaries, assumptions,
north-star metric, and pilot success criteria. Any unresolved decisions
are recorded explicitly rather than hidden in implementation.

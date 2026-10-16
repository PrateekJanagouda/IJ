// Friendly aliases over the generated OpenAPI types (src/lib/schema.d.ts — never edit that file;
// regenerate with `npm run gen:api` after backend API changes).
import type { components } from "./schema";

type S = components["schemas"];
export type Me = S["Me"];
export type Opportunity = S["Opportunity"];
export type OpportunityDetail = S["OpportunityDetail"];
export type Application = S["Application"];
export type Booking = S["Booking"];
export type Post = S["Post"];
export type Comment = S["Comment"];
export type Conversation = S["Conversation"];
export type Message = S["Message"];
export type Notification = S["Notification"];
export type Profile = S["Profile"];
export type ProfileList = S["ProfileList"];
export type EventT = S["Event"];
export type Genre = S["Genre"];

export type Page<T> = { next: string | null; previous: string | null; results: T[] };
export type OffsetPage<T> = { count: number; next: string | null; results: T[] };

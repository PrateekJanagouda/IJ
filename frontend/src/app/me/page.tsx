"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { GigCard } from "@/components/cards";
import { ProfileBody, ProfileHeader } from "@/components/profile-header";
import { Empty, Icon, Skeletons, SignInPrompt, Status, TopBar } from "@/components/ui";
import { api, ApiError, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { eventDate, timeAgo } from "@/lib/format";
import type { Application, Booking, Opportunity, Page, Profile } from "@/lib/types";

type Tab = "applications" | "bookings" | "listings" | "edit";

export default function MePage() {
  const { me, loading, logout, hasRole, refresh } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [tab, setTab] = useState<Tab>("applications");
  const [apps, setApps] = useState<Application[] | null>(null);
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [listings, setListings] = useState<Opportunity[] | null>(null);

  const load = useCallback(async () => {
    setProfile(await api<Profile>("/profiles/me"));
    if (hasRole("artist")) {
      api<Page<Application>>("/applications/mine").then((p) => setApps(p.results));
      api<Page<Booking>>("/bookings/mine").then((p) => setBookings(p.results));
    }
    if (hasRole("organizer")) api<Page<Opportunity>>("/opportunities/managed").then((p) => setListings(p.results));
  }, [hasRole]);

  useEffect(() => { if (me) load(); }, [me, load]);
  useEffect(() => { if (me && !hasRole("artist") && hasRole("organizer")) setTab("listings"); }, [me, hasRole]);

  if (loading) return null;
  if (!me) return (<><TopBar title="Me" /><SignInPrompt what="profile" /></>);

  const tabs: [Tab, string][] = [
    ...(hasRole("artist") ? [["applications", "Applied"], ["bookings", "Booked"]] as [Tab, string][] : []),
    ...(hasRole("organizer") ? [["listings", "My gigs"]] as [Tab, string][] : []),
    ["edit", "Edit"],
  ];

  return (
    <>
      <TopBar title="Me" right={
        <button className="icon-btn" aria-label="Sign out" onClick={async () => { await logout(); router.replace("/feed"); }}>
          <Icon name="logout" />
        </button>
      } />
      <div className="page">
        {!profile ? <Skeletons n={2} /> : <ProfileHeader profile={profile} />}
        <div className="segmented">
          {tabs.map(([k, t]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{t}</button>)}
        </div>

        {tab === "applications" && (apps === null ? <Skeletons /> : apps.length === 0 ?
          <Empty icon="🎤" title="No applications yet"><Link href="/gigs" className="btn sm primary" style={{ marginTop: 10 }}>Find gigs</Link></Empty> :
          apps.map((a) => (
            <Link key={a.id} href={`/gigs/${a.opportunity.id}`} className="card tap row">
              <div className="grow">
                <div className="bold ellipsis">{a.opportunity.title}</div>
                <div className="tiny faint">Applied {timeAgo(a.submitted_at)} ago</div>
              </div>
              <Status value={a.status} />
            </Link>
          )))}

        {tab === "bookings" && (bookings === null ? <Skeletons /> : bookings.length === 0 ?
          <Empty icon="🎟" title="No bookings yet">When a host accepts you, it shows up here.</Empty> :
          bookings.map((b) => <BookingRow key={b.id} booking={b} onChange={load} />))}

        {tab === "listings" && (
          <>
            <Link href="/gigs/new" className="btn primary block"><Icon name="plus" size={18} />Post a gig</Link>
            {listings === null ? <Skeletons /> : listings.length === 0 ? <Empty icon="📋" title="You haven't posted any gigs" /> :
              listings.map((g) => <GigCard key={g.id} gig={g} />)}
          </>
        )}

        {tab === "edit" && profile && <EditProfile profile={profile} onSaved={(p) => { setProfile(p); refresh(); }} />}
        {profile && tab !== "edit" && <ProfileBody profile={profile} />}
      </div>
    </>
  );
}

function BookingRow({ booking, onChange }: { booking: Booking; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const cancel = async () => {
    if (!confirm("Cancel this booking? The host will be notified.")) return;
    setBusy(true);
    try { await post(`/bookings/${booking.id}/cancel`, { reason: "Cancelled by artist" }); onChange(); } finally { setBusy(false); }
  };
  return (
    <div className="card col">
      <div className="row">
        <Link href={`/gigs/${booking.opportunity.id}`} className="grow bold ellipsis">{booking.opportunity.title}</Link>
        <Status value={booking.status} />
      </div>
      <div className="small muted">{eventDate(booking.opportunity.starts_at)}</div>
      {booking.status === "confirmed" && <button className="btn sm danger" onClick={cancel} disabled={busy}>Can&apos;t make it</button>}
    </div>
  );
}

function EditProfile({ profile, onSaved }: { profile: Profile; onSaved: (p: Profile) => void }) {
  const { hasRole } = useAuth();
  const artist = profile.artist;
  const [f, setF] = useState({
    display_name: profile.display_name, headline: profile.headline ?? "", bio: profile.bio ?? "",
    location_label: profile.location_label ?? "", visibility: profile.visibility,
    artist_name: artist?.artist_name ?? "",
  });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [link, setLink] = useState({ title: "", url: "" });

  const save = async () => {
    try {
      const { artist_name, ...core } = f;
      const body: Record<string, unknown> = { ...core };
      if (hasRole("artist")) body.artist = { artist_name };
      onSaved(await patch<Profile>("/profiles/me", body));
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.fieldMessage() ?? err.body.message : "Could not save." });
    }
  };
  const addLink = async () => {
    try {
      await post("/profiles/me/portfolio", { ...link, item_type: /youtu|vimeo/.test(link.url) ? "video" : /soundcloud|spotify|bandcamp/.test(link.url) ? "audio" : "link" });
      setLink({ title: "", url: "" });
      onSaved(await api<Profile>("/profiles/me"));
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.fieldMessage() ?? err.body.message : "Could not add." });
    }
  };

  return (
    <div className="col" style={{ gap: 12 }}>
      {msg && <div className={msg.ok ? "success" : "error"}>{msg.text}</div>}
      <div className="field"><label>Display name</label><input className="input" value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></div>
      {hasRole("artist") && <div className="field"><label>Stage name</label><input className="input" value={f.artist_name} onChange={(e) => setF({ ...f, artist_name: e.target.value })} /></div>}
      <div className="field"><label>Headline</label><input className="input" value={f.headline} maxLength={140} onChange={(e) => setF({ ...f, headline: e.target.value })} placeholder="Indie singer-songwriter · Bengaluru" /></div>
      <div className="field"><label>City</label><input className="input" value={f.location_label} onChange={(e) => setF({ ...f, location_label: e.target.value })} /></div>
      <div className="field"><label>Bio</label><textarea className="textarea" value={f.bio} onChange={(e) => setF({ ...f, bio: e.target.value })} /></div>
      <div className="field"><label>Who can see my profile</label>
        <select className="select" value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value as typeof f.visibility })}>
          <option value="public">Everyone</option><option value="members">Signed-in members</option><option value="private">Only me</option>
        </select></div>
      <button className="btn primary block" onClick={save}>Save profile</button>
      <div className="section-title">Add portfolio link</div>
      <input className="input" placeholder="Title (e.g. Live at Hard Rock)" value={link.title} onChange={(e) => setLink({ ...link, title: e.target.value })} />
      <input className="input" placeholder="https://youtube.com/…" inputMode="url" value={link.url} onChange={(e) => setLink({ ...link, url: e.target.value })} />
      <button className="btn ghost block" onClick={addLink} disabled={!link.title || !link.url}>Add link</button>
    </div>
  );
}

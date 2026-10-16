"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SignInPrompt, TopBar } from "@/components/ui";
import { api, ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Genre } from "@/lib/types";

const TYPES = [["open_mic_slot", "Open mic slot"], ["paid_gig", "Paid gig"], ["audition", "Audition"],
  ["band_slot", "Band slot"], ["dj_slot", "DJ slot"], ["host_role", "Host / MC"], ["other", "Other"]];
const COMP = [["unpaid", "Unpaid"], ["paid", "Paid"], ["revenue_share", "Revenue share"], ["negotiable", "Negotiable"]];

export default function NewGigPage() {
  const { me, hasRole, loading } = useAuth();
  const router = useRouter();
  const [genres, setGenres] = useState<Genre[]>([]);
  const [f, setF] = useState({
    title: "", description: "", opportunity_type: "open_mic_slot", compensation_type: "unpaid",
    compensation_amount: "", currency: "INR", capacity: 1, location_text: "", starts_at: "",
    application_deadline: "", requirements: "", genres: [] as string[],
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<Genre[]>("/genres").then(setGenres).catch(() => {}); }, []);
  if (loading) return null;
  if (!me) return (<><TopBar back title="Post a gig" /><SignInPrompt what="listings" /></>);
  if (!hasRole("organizer")) return (<><TopBar back title="Post a gig" /><div className="page"><div className="error">Add the organizer role from your profile to post gigs.</div></div></>);

  const set = (k: string, v: unknown) => setF((cur) => ({ ...cur, [k]: v }));

  const submit = async (publish: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        ...f,
        compensation_amount: f.compensation_type === "paid" && f.compensation_amount ? f.compensation_amount : null,
        currency: f.compensation_type === "paid" ? f.currency : "",
        starts_at: f.starts_at ? new Date(f.starts_at).toISOString() : null,
        application_deadline: f.application_deadline ? new Date(f.application_deadline).toISOString() : null,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };
      const gig = await post<{ id: string }>("/opportunities", body);
      if (publish) await post(`/opportunities/${gig.id}/publish`);
      router.replace(`/gigs/${gig.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.fieldMessage() ?? err.body.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar back title="Post a gig" />
      <div className="page" style={{ gap: 14 }}>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="field"><label>Title</label>
          <input className="input" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Friday acoustic open mic — 8 slots" maxLength={140} /></div>
        <div className="row">
          <div className="field grow"><label>Type</label>
            <select className="select" value={f.opportunity_type} onChange={(e) => set("opportunity_type", e.target.value)}>
              {TYPES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
          <div className="field" style={{ width: 96 }}><label>Spots</label>
            <input className="input" type="number" min={1} max={500} value={f.capacity} onChange={(e) => set("capacity", Number(e.target.value))} /></div>
        </div>
        <div className="row">
          <div className="field grow"><label>Pay</label>
            <select className="select" value={f.compensation_type} onChange={(e) => set("compensation_type", e.target.value)}>
              {COMP.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
          {f.compensation_type === "paid" && (
            <div className="field" style={{ width: 130 }}><label>Amount ({f.currency})</label>
              <input className="input" inputMode="decimal" value={f.compensation_amount} onChange={(e) => set("compensation_amount", e.target.value)} /></div>
          )}
        </div>
        <div className="field"><label>Where</label>
          <input className="input" value={f.location_text} onChange={(e) => set("location_text", e.target.value)} placeholder="Venue, area, city" /></div>
        <div className="row">
          <div className="field grow"><label>Performance</label>
            <input className="input" type="datetime-local" value={f.starts_at} onChange={(e) => set("starts_at", e.target.value)} /></div>
          <div className="field grow"><label>Apply by</label>
            <input className="input" type="datetime-local" value={f.application_deadline} onChange={(e) => set("application_deadline", e.target.value)} /></div>
        </div>
        <div className="field"><label>Description</label>
          <textarea className="textarea" value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="Set length, vibe, audience, what you provide…" /></div>
        <div className="field"><label>Requirements (optional)</label>
          <textarea className="textarea" style={{ minHeight: 64 }} value={f.requirements} onChange={(e) => set("requirements", e.target.value)} /></div>
        <div className="field"><label>Genres</label>
          <div className="chips" style={{ flexWrap: "wrap" }}>
            {genres.map((g) => (
              <button type="button" key={g.slug} className={`chip ${f.genres.includes(g.slug) ? "on" : ""}`}
                onClick={() => set("genres", f.genres.includes(g.slug) ? f.genres.filter((x) => x !== g.slug) : [...f.genres, g.slug])}>
                {g.name}</button>))}
          </div></div>
        <div className="row">
          <button className="btn ghost grow" disabled={busy} onClick={() => submit(false)}>Save draft</button>
          <button className="btn primary grow" disabled={busy} onClick={() => submit(true)}>Publish</button>
        </div>
      </div>
    </>
  );
}

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Avatar, Empty, Icon, Sheet, Skeletons, Status, TopBar } from "@/components/ui";
import { api, ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { compensation, deadline, eventDate, label } from "@/lib/format";
import type { OpportunityDetail } from "@/lib/types";

type PortfolioItem = { id: string; title: string; item_type: string };

export default function GigPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { me, hasRole } = useAuth();
  const [gig, setGig] = useState<OpportunityDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [applyOpen, setApplyOpen] = useState(false);
  const [note, setNote] = useState("");
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setGig(await api<OpportunityDetail>(`/opportunities/${id}`));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMissing(true);
    }
  }, [id]);

  useEffect(() => { load(); }, [load, me]);

  const openApply = async () => {
    if (!me) return router.push("/login");
    setApplyOpen(true);
    api<PortfolioItem[]>("/profiles/me/portfolio").then(setPortfolio).catch(() => {});
  };

  const apply = async () => {
    setBusy(true);
    setError(null);
    try {
      await post(`/opportunities/${id}/applications`, { cover_note: note, portfolio_item_ids: picked });
      setApplyOpen(false);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.fieldMessage() ?? err.body.message : "Could not apply.");
    } finally {
      setBusy(false);
    }
  };

  const message = async () => {
    if (!me) return router.push("/login");
    const c = await post<{ id: string }>("/conversations", { user_id: gig!.owner.id });
    router.push(`/inbox/${c.id}`);
  };

  if (missing) return (<><TopBar back title="Gig" /><Empty icon="🔒" title="This gig isn't available" /></>);
  if (!gig) return (<><TopBar back title="Gig" /><div className="page"><Skeletons n={3} /></div></>);

  const closes = deadline(gig.application_deadline);
  const myApp = gig.viewer_application;
  const stats = gig.manager_stats;

  let cta: React.ReactNode = null;
  if (gig.viewer_can_manage) {
    cta = <Link href={`/gigs/${gig.id}/applicants`} className="btn primary block">Review applicants</Link>;
  } else if (myApp) {
    cta = <Link href="/me" className="btn ghost block">Your application: <Status value={myApp.status} /></Link>;
  } else if (gig.accepting_applications) {
    cta = me && !hasRole("artist")
      ? <button className="btn ghost block" disabled>Add the artist role to apply</button>
      : <button className="btn primary block" onClick={openApply}>Apply now</button>;
  } else {
    cta = <button className="btn ghost block" disabled>Not accepting applications</button>;
  }

  return (
    <>
      <TopBar back title="" right={
        <button className="icon-btn" aria-label="Share" onClick={() => navigator.share?.({ url: gig.share_url }) ?? navigator.clipboard.writeText(gig.share_url)}>
          <Icon name="share" />
        </button>
      } />
      <div className="page" style={{ paddingBottom: 100 }}>
        <div className="hero">
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            <span className="tag spot">{label(gig.opportunity_type)}</span>
            <Status value={gig.status} />
          </div>
          <h2>{gig.title}</h2>
          {gig.event && <div className="muted small">Part of <b style={{ color: "var(--text)" }}>{gig.event.title}</b></div>}
          <div className="col small" style={{ marginTop: 12, gap: 8 }}>
            <div className="row"><Icon name="clock" size={17} />{eventDate(gig.starts_at ?? gig.event?.starts_at, gig.timezone)}</div>
            <div className="row"><Icon name="pin" size={17} />{gig.is_online ? "Online" : gig.location_text || "Location in event details"}</div>
          </div>
        </div>

        <div className="card row" style={{ justifyContent: "space-around" }}>
          <div className="stat"><b className="pay">{compensation(gig.compensation_type, gig.compensation_amount, gig.currency)}</b><span className="tiny muted">Pay</span></div>
          <div className="stat"><b>{gig.capacity}</b><span className="tiny muted">{gig.capacity === 1 ? "Spot" : "Spots"}</span></div>
          <div className="stat"><b style={{ fontSize: 14, paddingTop: 3 }}>{closes ?? "Open"}</b><span className="tiny muted">Deadline</span></div>
        </div>

        {stats && (
          <div className="card">
            <div className="small muted bold" style={{ marginBottom: 8 }}>Your listing</div>
            <div className="row" style={{ justifyContent: "space-between" }}>
              {(["submitted", "shortlisted", "accepted", "declined"] as const).map((s) => (
                <div key={s} className="stat"><b>{stats.applications[s] ?? 0}</b><span className="tiny muted">{label(s)}</span></div>
              ))}
            </div>
            <div className="tiny muted" style={{ marginTop: 8 }}>{stats.confirmed_bookings}/{gig.capacity} spots confirmed</div>
          </div>
        )}

        <div className="section-title">About</div>
        <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{gig.description}</p>
        {gig.requirements && (<><div className="section-title">Requirements</div><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{gig.requirements}</p></>)}
        {gig.genres.length > 0 && (
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {gig.genres.map((g) => <span key={g} className="tag">#{g}</span>)}
            {gig.skills.map((s) => <span key={s} className="tag">{s}</span>)}
          </div>
        )}

        <div className="section-title">Hosted by</div>
        <div className="card row">
          <Avatar id={gig.owner.id} name={gig.owner.display_name} />
          <Link href={gig.owner.profile_id ? `/profiles/${gig.owner.profile_id}` : "#"} className="grow bold">{gig.owner.display_name}</Link>
          {!gig.viewer_can_manage && <button className="btn sm ghost" onClick={message}><Icon name="inbox" size={16} />Message</button>}
        </div>
      </div>

      <div className="actionbar">{cta}</div>

      <Sheet open={applyOpen} onClose={() => setApplyOpen(false)}>
        <h3 style={{ margin: "0 0 4px" }}>Apply to {gig.title}</h3>
        <p className="muted small" style={{ marginTop: 0 }}>The host sees your profile, note and selected work.</p>
        {error && <div className="error" style={{ marginBottom: 10 }}>{error}</div>}
        <div className="field">
          <label htmlFor="note">Note to the host</label>
          <textarea id="note" className="textarea" maxLength={4000} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="What would you perform? Set length, gear, availability…" />
        </div>
        {portfolio.length > 0 && (
          <div className="col" style={{ marginTop: 12 }}>
            <span className="small muted bold">Attach work</span>
            {portfolio.map((p) => (
              <label key={p.id} className="card row" style={{ padding: 10, cursor: "pointer" }}>
                <input type="checkbox" checked={picked.includes(p.id)}
                  onChange={() => setPicked((cur) => cur.includes(p.id) ? cur.filter((x) => x !== p.id) : [...cur, p.id])} />
                <span className="grow">{p.title}</span><span className="tag">{p.item_type}</span>
              </label>
            ))}
          </div>
        )}
        <button className="btn primary block" style={{ marginTop: 16 }} onClick={apply} disabled={busy}>
          {busy ? "Sending…" : "Send application"}
        </button>
      </Sheet>
    </>
  );
}

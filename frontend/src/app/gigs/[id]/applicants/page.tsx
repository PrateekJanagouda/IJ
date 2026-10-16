"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Avatar, Empty, Icon, Skeletons, Status, TopBar } from "@/components/ui";
import { api, ApiError, post } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { Application, OpportunityDetail, Page } from "@/lib/types";

const FILTERS = ["", "submitted", "shortlisted", "accepted", "declined"] as const;

export default function ApplicantsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [gig, setGig] = useState<OpportunityDetail | null>(null);
  const [apps, setApps] = useState<Application[] | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("");
  const [toast, setToast] = useState<{ ok: boolean; text: string } | null>(null);
  const [denied, setDenied] = useState(false);

  const load = useCallback(async () => {
    try {
      const [g, page] = await Promise.all([
        api<OpportunityDetail>(`/opportunities/${id}`),
        api<Page<Application>>(`/opportunities/${id}/applications${filter ? `?status=${filter}` : ""}`),
      ]);
      setGig(g);
      setApps(page.results);
    } catch (err) {
      if (err instanceof ApiError && [403, 404].includes(err.status)) setDenied(true);
    }
  }, [id, filter]);

  useEffect(() => { load(); }, [load]);

  const act = async (appId: string, action: "shortlist" | "accept" | "decline") => {
    try {
      await post(`/applications/${appId}/${action}`);
      const done = { accept: "Booked! The artist has been notified.", shortlist: "Shortlisted.", decline: "Declined." };
      setToast({ ok: true, text: done[action] });
      load();
    } catch (err) {
      // e.g. 409 capacity_full when the last spot was just taken by a co-manager.
      setToast({ ok: false, text: err instanceof ApiError ? err.body.message : "Something went wrong." });
    }
    setTimeout(() => setToast(null), 2600);
  };

  const message = async (userId: string) => {
    const c = await post<{ id: string }>("/conversations", { user_id: userId });
    router.push(`/inbox/${c.id}`);
  };

  if (denied) return (<><TopBar back title="Applicants" /><Empty icon="🔒" title="Only this gig's hosts can see applicants" /></>);

  const stats = gig?.manager_stats;
  return (
    <>
      <TopBar back title="Applicants" />
      <div className="page">
        {gig && (
          <div className="card">
            <div className="bold ellipsis">{gig.title}</div>
            <div className="small muted">{stats?.confirmed_bookings ?? 0} of {gig.capacity} spots booked</div>
            <div style={{ height: 6, background: "var(--surface-2)", borderRadius: 9, marginTop: 8, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${Math.min(100, ((stats?.confirmed_bookings ?? 0) / gig.capacity) * 100)}%`, background: "var(--ok)" }} />
            </div>
          </div>
        )}
        {toast && <div className={toast.ok ? "success" : "error"} role="status">{toast.text}</div>}
        <div className="chips">
          {FILTERS.map((f) => (
            <button key={f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>
              {f ? f[0].toUpperCase() + f.slice(1) : "All"}
            </button>
          ))}
        </div>
        {apps === null ? <Skeletons /> : apps.length === 0 ? <Empty icon="📭" title="No applicants here yet" /> :
          apps.map((a) => {
            const open = a.status === "submitted" || a.status === "shortlisted";
            return (
              <div key={a.id} className="card col" style={{ gap: 10 }}>
                <div className="row">
                  <Avatar id={a.applicant.id} name={a.applicant.display_name} />
                  <div className="grow">
                    <Link href={a.applicant.profile_id ? `/profiles/${a.applicant.profile_id}` : "#"} className="bold">{a.applicant.display_name}</Link>
                    <div className="tiny faint">Applied {timeAgo(a.submitted_at)} ago</div>
                  </div>
                  <Status value={a.status} />
                </div>
                {a.cover_note && <p className="small clamp-3" style={{ margin: 0 }}>“{a.cover_note}”</p>}
                {a.portfolio_items.length > 0 && (
                  <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                    {a.portfolio_items.map((p) => (
                      <a key={p.id} href={p.url} target="_blank" rel="noopener noreferrer nofollow" className="tag spot">▶ {p.title}</a>
                    ))}
                  </div>
                )}
                <div className="row" style={{ gap: 8 }}>
                  {open && <button className="btn sm primary grow" onClick={() => act(a.id, "accept")}><Icon name="check" size={16} />Book</button>}
                  {a.status === "submitted" && <button className="btn sm grow" onClick={() => act(a.id, "shortlist")}>Shortlist</button>}
                  {open && <button className="btn sm danger grow" onClick={() => act(a.id, "decline")}>Decline</button>}
                  <button className="btn sm ghost" onClick={() => message(a.applicant.id)} aria-label={`Message ${a.applicant.display_name}`}>
                    <Icon name="inbox" size={17} />
                  </button>
                </div>
              </div>
            );
          })}
      </div>
    </>
  );
}

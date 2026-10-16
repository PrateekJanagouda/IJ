"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Avatar, Empty, Skeletons, SignInPrompt, TopBar } from "@/components/ui";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import type { Notification, Page } from "@/lib/types";

function describe(n: Notification): { text: React.ReactNode; href: string } {
  const who = <b>{n.actor?.display_name ?? "Someone"}</b>;
  const p = (n.payload ?? {}) as Record<string, string>;
  const gig = <b>{p.opportunity_title}</b>;
  switch (n.notification_type) {
    case "application.submitted": return { text: <>{who} applied to {gig}</>, href: `/gigs/${p.opportunity_id}/applicants` };
    case "application.shortlisted": return { text: <>You were shortlisted for {gig} ✨</>, href: `/gigs/${p.opportunity_id}` };
    case "application.accepted": return { text: <>You&apos;re booked for {gig} 🎉</>, href: "/me" };
    case "application.declined": return { text: <>Your application to {gig} wasn&apos;t selected</>, href: "/me" };
    case "application.withdrawn": return { text: <>{who} withdrew from {gig}</>, href: `/gigs/${p.opportunity_id}/applicants` };
    case "booking.cancelled": return { text: <>{who} cancelled the booking for {gig}</>, href: `/gigs/${p.opportunity_id}` };
    case "booking.completed": return { text: <>Performance at {gig} marked complete</>, href: "/me" };
    case "opportunity.cancelled": return { text: <><b>{p.opportunity_title}</b> was cancelled</>, href: "/me" };
    case "event.cancelled": return { text: <><b>{p.event_title}</b> was cancelled — the host is reviewing your slot</>, href: "/me" };
    case "message.received": return { text: <>New messages from {who}</>, href: `/inbox/${n.resource_id}` };
    case "post.liked": return { text: <>{who} liked your post</>, href: `/posts/${n.resource_id}` };
    case "post.commented": return { text: <>{who} commented on your post</>, href: `/posts/${n.resource_id}` };
    case "post.reposted": return { text: <>{who} reposted your post</>, href: `/posts/${n.resource_id}` };
    case "user.followed": return { text: <>{who} started following you</>, href: n.actor?.profile_id ? `/profiles/${n.actor.profile_id}` : "#" };
    default: return { text: n.notification_type, href: "#" };
  }
}

export default function AlertsPage() {
  const { me, loading } = useAuth();
  const [items, setItems] = useState<Notification[] | null>(null);

  const load = () => api<Page<Notification>>("/notifications").then((p) => setItems(p.results)).catch(() => {});
  useEffect(() => { if (me) load(); }, [me]);

  if (loading) return null;
  if (!me) return (<><TopBar title="Alerts" /><SignInPrompt what="notifications" /></>);

  const open = (n: Notification) => { if (!n.is_read) post(`/notifications/${n.id}/read`).catch(() => {}); };
  const readAll = async () => { await post("/notifications/read-all"); load(); };

  return (
    <>
      <TopBar title="Alerts" right={items?.some((n) => !n.is_read) && <button className="btn sm ghost" onClick={readAll}>Mark all read</button>} />
      <div className="page" style={{ gap: 0 }}>
        {items === null ? <Skeletons /> : items.length === 0 ? <Empty icon="🔔" title="You're all caught up" /> :
          items.map((n) => {
            const { text, href } = describe(n);
            return (
              <Link key={n.id} href={href} onClick={() => open(n)} className="row"
                style={{ padding: "12px 4px", borderBottom: "1px solid var(--line)", alignItems: "flex-start" }}>
                <Avatar id={n.actor?.id} name={n.actor?.display_name ?? "EQ"} size="sm" />
                <div className="grow small" style={{ color: n.is_read ? "var(--muted)" : "var(--text)" }}>
                  {text}
                  <div className="tiny faint">{timeAgo(n.created_at)}</div>
                </div>
                {!n.is_read && <span className="unread-dot" style={{ marginTop: 6 }} />}
              </Link>
            );
          })}
      </div>
    </>
  );
}

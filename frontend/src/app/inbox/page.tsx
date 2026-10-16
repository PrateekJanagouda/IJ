"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Avatar, Empty, Skeletons, SignInPrompt, TopBar } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import type { Conversation, OffsetPage } from "@/lib/types";

export default function InboxPage() {
  const { me, loading } = useAuth();
  const [convos, setConvos] = useState<Conversation[] | null>(null);

  useEffect(() => {
    if (!me) return;
    const load = () => api<OffsetPage<Conversation>>("/conversations").then((p) => setConvos(p.results)).catch(() => {});
    load();
    const t = setInterval(load, 10_000);
    return () => clearInterval(t);
  }, [me]);

  if (loading) return null;
  if (!me) return (<><TopBar title="Inbox" /><SignInPrompt what="messages" /></>);

  return (
    <>
      <TopBar title="Inbox" />
      <div className="page" style={{ gap: 2 }}>
        {convos === null ? <Skeletons /> : convos.length === 0 ? (
          <Empty icon="💬" title="No conversations yet">Message a host from any gig, or an artist from their profile.</Empty>
        ) : convos.map((c) => {
          const other = c.participants.find((p) => p.id !== me.id) ?? c.participants[0];
          const last = c.last_message;
          const unread = c.unread_count ?? 0;
          return (
            <Link key={c.id} href={`/inbox/${c.id}`} className="row" style={{ padding: "12px 4px", borderBottom: "1px solid var(--line)" }}>
              <Avatar id={other.id} name={other.display_name} />
              <div className="grow">
                <div className="row" style={{ gap: 6 }}>
                  <span className={`grow ellipsis ${unread ? "bold" : ""}`}>{other.display_name}</span>
                  <span className="tiny faint">{timeAgo(c.last_message_at ?? c.created_at)}</span>
                </div>
                <div className={`small ellipsis ${unread ? "" : "muted"}`}>
                  {last ? (last.is_deleted ? <i>Message deleted</i> : `${last.sender_id === me.id ? "You: " : ""}${last.preview}`) : "Say hello 👋"}
                </div>
              </div>
              {unread > 0 && <span className="badge-dot" style={{ position: "static", border: 0 }}>{unread}</span>}
            </Link>
          );
        })}
      </div>
    </>
  );
}

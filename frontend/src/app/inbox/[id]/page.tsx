"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Avatar, Empty, TopBar } from "@/components/ui";
import { api, ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Conversation, Message, Page } from "@/lib/types";

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const [convo, setConvo] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const [c, page] = await Promise.all([
        api<Conversation>(`/conversations/${id}`),
        api<Page<Message>>(`/conversations/${id}/messages`),
      ]);
      setConvo(c);
      setMessages(page.results.slice().reverse()); // API is newest-first; chat reads oldest-first
      post(`/conversations/${id}/read`).catch(() => {});
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMissing(true);
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5_000); // polling; WebSockets later deliver the same persisted rows
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => { bottom.current?.scrollIntoView(); }, [messages.length]);

  const send = async () => {
    const body = draft.trim();
    if (!body) return;
    setDraft("");
    setError(null);
    try {
      await post(`/conversations/${id}/messages`, { body });
      load();
    } catch (err) {
      setDraft(body); // don't lose what they typed
      setError(err instanceof ApiError ? err.body.message : "Not sent.");
    }
  };

  if (missing) return (<><TopBar back title="Chat" /><Empty icon="🔒" title="Conversation not found" /></>);
  const other = convo?.participants.find((p) => p.id !== me?.id);

  return (
    <>
      <TopBar back title={other ? (
        <Link href={other.profile_id ? `/profiles/${other.profile_id}` : "#"} className="row" style={{ gap: 10 }}>
          <Avatar id={other.id} name={other.display_name} size="sm" />
          <span className="ellipsis">{other.display_name}</span>
        </Link>
      ) : "Chat"} />
      <div className="thread">
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.sender.id === me?.id ? "me" : "them"} ${m.is_deleted ? "deleted" : ""}`}>
            {m.is_deleted ? "Message deleted" : m.body}
          </div>
        ))}
        {error && <div className="error">{error}</div>}
        <div ref={bottom} />
      </div>
      <div className="composer">
        <input className="input" placeholder="Message…" value={draft} maxLength={5000}
          onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} aria-label="Message" />
        <button className="btn primary" onClick={send} disabled={!draft.trim()}>Send</button>
      </div>
    </>
  );
}

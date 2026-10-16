"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PostCard } from "@/components/cards";
import { Avatar, Empty, Icon, Skeletons, TopBar } from "@/components/ui";
import { api, ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Page, Post } from "@/lib/types";

export default function FeedPage() {
  const { me, loading } = useAuth();
  const [tab, setTab] = useState<"following" | "discover">("following");
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const source = !me || tab === "discover" ? "/feed/discover" : "/feed";

  const load = useCallback(async () => {
    const page = await api<Page<Post>>(source);
    setPosts(page.results);
    setNext(page.next);
  }, [source]);

  useEffect(() => { if (!loading) load(); }, [load, loading]);

  const loadMore = async () => {
    if (!next) return;
    const url = new URL(next);
    const page = await api<Page<Post>>(`${source}?${url.searchParams}`);
    setPosts((cur) => [...(cur ?? []), ...page.results]);
    setNext(page.next);
  };

  const publish = async () => {
    if (!draft.trim()) return;
    setError(null);
    try {
      await post("/posts", { body: draft });
      setDraft("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.body.message : "Could not post.");
    }
  };

  return (
    <>
      <TopBar right={!me && <Link href="/login" className="btn sm primary">Sign in</Link>} />
      <div className="page">
        {me && (
          <>
            <div className="segmented">
              <button className={tab === "following" ? "on" : ""} onClick={() => setTab("following")}>Following</button>
              <button className={tab === "discover" ? "on" : ""} onClick={() => setTab("discover")}>Discover</button>
            </div>
            <div className="card row" style={{ alignItems: "flex-start" }}>
              <Avatar id={me.id} name={me.display_name} />
              <div className="grow col">
                <textarea className="textarea" placeholder="Share a new release, a gig, a moment…"
                  value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={5000}
                  style={{ minHeight: 64, background: "transparent", border: 0, padding: "8px 0" }} />
                {error && <div className="error">{error}</div>}
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <button className="btn sm primary" disabled={!draft.trim()} onClick={publish}>Post</button>
                </div>
              </div>
            </div>
          </>
        )}
        {!me && !loading && (
          <div className="hero">
            <span className="tag spot">Live music network</span>
            <h2>Every artist deserves a stage.</h2>
            <p className="muted small" style={{ margin: "0 0 14px" }}>Find open mics, paid gigs and auditions — and the people behind them.</p>
            <div className="row">
              <Link href="/register" className="btn primary grow">Join free</Link>
              <Link href="/gigs" className="btn ghost grow"><Icon name="gigs" size={18} />Browse gigs</Link>
            </div>
          </div>
        )}
        {posts === null ? <Skeletons /> : posts.length === 0 ? (
          <Empty icon="🎧" title="Your feed is quiet">
            Follow artists and venues to see their posts here. <br />
            <button className="btn sm ghost" style={{ marginTop: 12 }} onClick={() => setTab("discover")}>Discover people</button>
          </Empty>
        ) : posts.map((p) => <PostCard key={p.id} post={p} onChange={load} />)}
        {next && <button className="btn ghost block" onClick={loadMore}>Load more</button>}
      </div>
    </>
  );
}

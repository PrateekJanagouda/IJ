"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PostCard } from "@/components/cards";
import { Avatar, Empty, Skeletons, TopBar } from "@/components/ui";
import { api, ApiError, post as apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import type { Comment, Page, Post } from "@/lib/types";

export default function PostPage() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [missing, setMissing] = useState(false);
  const [draft, setDraft] = useState("");

  const load = useCallback(async () => {
    try {
      const [p, c] = await Promise.all([
        api<Post>(`/posts/${id}`),
        api<Page<Comment>>(`/posts/${id}/comments`),
      ]);
      setPost(p);
      setComments(c.results);
    } catch (err) {
      // A share link never bypasses visibility: private, deleted or hidden posts are a 404.
      if (err instanceof ApiError && err.status === 404) setMissing(true);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const send = async () => {
    if (!draft.trim()) return;
    await apiPost(`/posts/${id}/comments`, { body: draft });
    setDraft("");
    load();
  };

  return (
    <>
      <TopBar back title="Post" />
      <div className="page" style={{ paddingBottom: 90 }}>
        {missing ? <Empty icon="🔒" title="This post isn't available">It may be private or removed.</Empty>
          : !post ? <Skeletons n={1} /> : (
            <>
              <PostCard post={post} onChange={load} />
              <div className="section-title">Comments</div>
              {comments.length === 0 && <p className="muted small">No comments yet.</p>}
              {comments.map((c) => (
                <div key={c.id} className="row" style={{ alignItems: "flex-start" }}>
                  <Avatar id={c.author.id} name={c.author.display_name} size="sm" />
                  <div className="grow" style={{ background: "var(--surface)", borderRadius: 14, padding: "8px 12px" }}>
                    <div className="small"><b>{c.author.display_name}</b> <span className="faint">· {timeAgo(c.created_at)}</span></div>
                    <div>{c.body}</div>
                  </div>
                </div>
              ))}
            </>
          )}
      </div>
      {me && post && (
        <div className="composer">
          <input className="input" placeholder="Add a comment…" value={draft} maxLength={2000}
            onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
          <button className="btn primary" onClick={send} disabled={!draft.trim()}>Reply</button>
        </div>
      )}
    </>
  );
}

"use client";

import Link from "next/link";
import { useState } from "react";
import { del, post as apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { compensation, deadline, label, timeAgo } from "@/lib/format";
import type { Opportunity, Post } from "@/lib/types";
import { Avatar, Icon } from "./ui";

export function GigCard({ gig }: { gig: Opportunity }) {
  const when = gig.starts_at ?? gig.event?.starts_at;
  const d = when ? new Date(when) : null;
  const closes = deadline(gig.application_deadline);
  return (
    <Link href={`/gigs/${gig.id}`} className="card tap row" style={{ alignItems: "flex-start", gap: 12 }}>
      <div className="gig-when">
        {d ? (
          <>
            <div className="d">{d.getDate()}</div>
            <div className="m">{d.toLocaleString(undefined, { month: "short" })}</div>
          </>
        ) : <div className="m">TBA</div>}
      </div>
      <div className="grow col" style={{ gap: 4 }}>
        <div className="bold ellipsis">{gig.title}</div>
        <div className="small muted ellipsis">
          {gig.event ? `${gig.event.title} · ` : ""}{gig.owner.display_name}
        </div>
        <div className="row small" style={{ gap: 8, flexWrap: "wrap" }}>
          <span className="pay">{compensation(gig.compensation_type, gig.compensation_amount, gig.currency)}</span>
          <span className="faint">•</span>
          <span className="muted row" style={{ gap: 3 }}><Icon name="pin" size={13} />{gig.is_online ? "Online" : gig.location_text || "See details"}</span>
        </div>
        <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 2 }}>
          <span className="tag">{label(gig.opportunity_type)}</span>
          {gig.genres.slice(0, 2).map((g) => <span key={g} className="tag">#{g}</span>)}
          {closes && gig.accepting_applications && <span className="tag spot">{closes}</span>}
        </div>
      </div>
    </Link>
  );
}

export function PostCard({ post, onChange }: { post: Post; onChange?: () => void }) {
  const { me } = useAuth();
  const [liked, setLiked] = useState(!!post.viewer_has_liked);
  const [likes, setLikes] = useState(post.like_count ?? 0);
  const [copied, setCopied] = useState(false);
  const original = post.repost_of;

  const toggleLike = async () => {
    if (!me) return (window.location.href = "/login");
    // Optimistic update, rolled back if the server refuses (e.g. a block).
    const next = !liked;
    setLiked(next);
    setLikes((n) => n + (next ? 1 : -1));
    try {
      if (next) await apiPost(`/posts/${post.id}/like`);
      else await del(`/posts/${post.id}/like`);
    } catch {
      setLiked(!next);
      setLikes((n) => n + (next ? -1 : 1));
    }
  };

  const repost = async () => {
    if (!me) return (window.location.href = "/login");
    try {
      await apiPost(`/posts/${(original?.id ?? post.id)}/repost`);
      onChange?.();
    } catch { /* already reposted, or not shareable */ }
  };

  const share = async () => {
    try {
      if (navigator.share) await navigator.share({ url: post.share_url });
      else { await navigator.clipboard.writeText(post.share_url); setCopied(true); setTimeout(() => setCopied(false), 1500); }
    } catch { /* user dismissed */ }
  };

  // Plain repost: render the original under a "X reposted" line.
  // Quote repost: the reposter's own words lead; the original sits in a quote box.
  const plainRepost = !!original && !post.body;
  const author = plainRepost && original?.author ? original.author : post.author;
  return (
    <article className="card">
      {plainRepost && (
        <div className="row tiny muted" style={{ marginBottom: 8, gap: 6 }}>
          <Icon name="repost" size={14} /> {post.author.display_name} reposted
        </div>
      )}
      <div className="row" style={{ alignItems: "flex-start" }}>
        <Link href={author.profile_id ? `/profiles/${author.profile_id}` : "#"}>
          <Avatar id={author.id} name={author.display_name} />
        </Link>
        <div className="grow">
          <div className="row" style={{ gap: 6 }}>
            <span className="bold ellipsis">{author.display_name}</span>
            <span className="faint small">· {timeAgo(post.created_at)}</span>
            {post.visibility === "followers" && <span className="tag" style={{ height: 20 }}>Followers</span>}
          </div>
          {original ? (
            <>
              {post.body && <p style={{ margin: "4px 0 0", whiteSpace: "pre-wrap" }}>{post.body}</p>}
              <div className={post.body ? "quote" : ""} style={post.body ? {} : { marginTop: 4 }}>
                {original.unavailable ? <span className="muted small">This post is no longer available.</span> : (
                  <>
                    {post.body && original.author && (
                      <div className="row small" style={{ gap: 8, marginBottom: 4 }}>
                        <Avatar id={original.author.id} name={original.author.display_name} size="sm" />
                        <b>{original.author.display_name}</b>
                      </div>
                    )}
                    <span style={{ whiteSpace: "pre-wrap" }}>{original.body}</span>
                  </>
                )}
              </div>
            </>
          ) : (
            <p style={{ margin: "4px 0 0", whiteSpace: "pre-wrap" }}>{post.body}</p>
          )}
          <div className="post-actions">
            <button className={liked ? "on" : ""} onClick={toggleLike} aria-label="Like">
              <Icon name="heart" size={18} fill={liked} /> {likes || ""}
            </button>
            <Link href={`/posts/${post.id}`}><button aria-label="Comments"><Icon name="comment" size={18} /> {post.comment_count || ""}</button></Link>
            <button onClick={repost} aria-label="Repost"><Icon name="repost" size={18} /></button>
            <button onClick={share} aria-label="Share"><Icon name="share" size={18} />{copied ? "Copied" : ""}</button>
          </div>
        </div>
      </div>
    </article>
  );
}

"use client";

import type { Profile } from "@/lib/types";
import { Avatar } from "./ui";

export function ProfileHeader({ profile, actions }: { profile: Profile; actions?: React.ReactNode }) {
  const artist = profile.artist;
  return (
    <div className="hero" style={{ textAlign: "center" }}>
      <div style={{ display: "flex", justifyContent: "center" }}>
        <Avatar id={profile.user_id} name={profile.display_name} size="lg" />
      </div>
      <h2 style={{ marginTop: 10 }}>{artist?.artist_name || profile.display_name}</h2>
      {profile.headline && <div className="muted small">{profile.headline}</div>}
      <div className="row" style={{ justifyContent: "center", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
        {profile.roles.map((r) => <span key={r} className="tag spot" style={{ textTransform: "capitalize" }}>{r}</span>)}
        {profile.location_label && <span className="tag">📍 {profile.location_label}</span>}
      </div>
      <div className="row" style={{ justifyContent: "center", gap: 28, marginTop: 14 }}>
        <div className="stat"><b>{profile.follower_count}</b><span className="tiny muted">Followers</span></div>
        <div className="stat"><b>{profile.following_count}</b><span className="tiny muted">Following</span></div>
        <div className="stat"><b>{profile.portfolio?.length ?? 0}</b><span className="tiny muted">Works</span></div>
      </div>
      {actions && <div className="row" style={{ marginTop: 14 }}>{actions}</div>}
    </div>
  );
}

export function ProfileBody({ profile }: { profile: Profile }) {
  const artist = profile.artist;
  const portfolio = profile.portfolio ?? [];
  return (
    <>
      {profile.bio && (<><div className="section-title">About</div><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{profile.bio}</p></>)}
      {artist && ((artist.genres?.length ?? 0) > 0 || (artist.skills?.length ?? 0) > 0) && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {artist.genres?.map((g) => <span key={g} className="tag">#{g}</span>)}
          {artist.skills?.map((s) => <span key={s} className="tag">{s}</span>)}
        </div>
      )}
      {portfolio.length > 0 && (
        <>
          <div className="section-title">Portfolio</div>
          {portfolio.map((p) => (
            <a key={p.id} href={p.url} target="_blank" rel="noopener noreferrer nofollow" className="card tap row">
              <div className="gig-when" style={{ width: 44, height: 44 }}>{p.item_type === "audio" ? "🎧" : p.item_type === "video" ? "🎬" : p.item_type === "image" ? "🖼" : "🔗"}</div>
              <div className="grow"><div className="bold ellipsis">{p.title}</div><div className="tiny faint ellipsis">{new URL(p.url).hostname}</div></div>
            </a>
          ))}
        </>
      )}
    </>
  );
}

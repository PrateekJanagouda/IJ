"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { initials, label } from "@/lib/format";

/* ---------- Icons (inline SVG, no icon font download) ---------- */
const paths: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  gigs: "M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12-2a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  inbox: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z",
  bell: "M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0",
  user: "M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
  heart: "M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3C14.7 3 13.5 3.5 12 5c-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7Z",
  comment: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  repost: "m17 1 4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4m14-2v2a4 4 0 0 1-4 4H3",
  share: "M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13",
  back: "M15 18l-6-6 6-6",
  plus: "M12 5v14M5 12h14",
  pin: "M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11Zm0-8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-14v4l3 2",
  send: "m22 2-7 20-4-9-9-4Z M22 2 11 13",
  check: "M20 6 9 17l-5-5",
  flag: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
  search: "m21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
};

export function Icon({ name, size = 22, fill = false }: { name: keyof typeof paths | string; size?: number; fill?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill ? "currentColor" : "none"}
      stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={paths[name]} />
    </svg>
  );
}

/* ---------- Avatar: deterministic colour from the user id ---------- */
const HUES = [12, 28, 42, 160, 200, 262, 292, 330];
export function Avatar({ id, name, size = "" }: { id?: string | null; name?: string | null; size?: "" | "sm" | "lg" }) {
  const n = (id ?? name ?? "x").split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const hue = HUES[n % HUES.length];
  return (
    <div className={`avatar ${size}`}
      style={{ background: `linear-gradient(135deg, hsl(${hue} 80% 58%), hsl(${(hue + 40) % 360} 70% 42%))` }}>
      {initials(name)}
    </div>
  );
}

export function Status({ value }: { value: string }) {
  return <span className={`tag status ${value}`}>{label(value)}</span>;
}

export function TopBar({ title, back, right }: { title?: React.ReactNode; back?: boolean; right?: React.ReactNode }) {
  const router = useRouter();
  return (
    <header className="topbar">
      {back && (
        <button className="icon-btn" aria-label="Back" onClick={() => router.back()} style={{ marginLeft: -8 }}>
          <Icon name="back" />
        </button>
      )}
      <h1>{title ?? <span className="brand">EQ<span>ora</span></span>}</h1>
      {right}
    </header>
  );
}

/* ---------- Bottom navigation with live unread badges ---------- */
export function BottomNav() {
  const path = usePathname();
  const { me } = useAuth();
  const [unread, setUnread] = useState({ messages: 0, alerts: 0 });

  useEffect(() => {
    if (!me) return;
    let alive = true;
    const load = async () => {
      try {
        const [m, n] = await Promise.all([
          api<{ unread: number }>("/conversations/unread-count"),
          api<{ unread: number }>("/notifications/unread-count"),
        ]);
        if (alive) setUnread({ messages: m.unread, alerts: n.unread });
      } catch { /* badge is best-effort */ }
    };
    load();
    const t = setInterval(load, 20_000); // polling until WebSockets land (see mvp-decisions.md)
    return () => { alive = false; clearInterval(t); };
  }, [me, path]);

  const tabs = [
    { href: "/feed", icon: "home", text: "Feed" },
    { href: "/gigs", icon: "gigs", text: "Gigs" },
    { href: "/inbox", icon: "inbox", text: "Inbox", count: unread.messages },
    { href: "/alerts", icon: "bell", text: "Alerts", count: unread.alerts },
    { href: "/me", icon: "user", text: "Me" },
  ];
  return (
    <nav className="bottomnav" aria-label="Main">
      {tabs.map((t) => (
        <Link key={t.href} href={t.href} className={path.startsWith(t.href) ? "active" : ""}>
          <Icon name={t.icon} />
          {t.text}
          {!!t.count && <span className="badge-dot">{t.count > 9 ? "9+" : t.count}</span>}
        </Link>
      ))}
    </nav>
  );
}

export function Sheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true">
        <div className="grabber" />
        {children}
      </div>
    </>
  );
}

export function Empty({ icon, title, children }: { icon: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <div className="big">{icon}</div>
      <div className="bold" style={{ color: "var(--text)" }}>{title}</div>
      {children && <div className="small" style={{ marginTop: 6 }}>{children}</div>}
    </div>
  );
}

export function Skeletons({ n = 3 }: { n?: number }) {
  return <>{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" />)}</>;
}

/** Shown in place of member-only screens when signed out. */
export function SignInPrompt({ what }: { what: string }) {
  return (
    <div className="page">
      <div className="hero">
        <div className="tag spot">Members</div>
        <h2>Sign in to see your {what}</h2>
        <p className="muted small" style={{ margin: "0 0 14px" }}>
          Join artists, organizers and venues finding each other every night.
        </p>
        <div className="row">
          <Link href="/login" className="btn primary grow">Sign in</Link>
          <Link href="/register" className="btn ghost grow">Create account</Link>
        </div>
      </div>
    </div>
  );
}

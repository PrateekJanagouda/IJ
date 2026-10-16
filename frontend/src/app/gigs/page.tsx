"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { GigCard } from "@/components/cards";
import { Empty, Icon, Skeletons, TopBar } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Genre, Opportunity, Page } from "@/lib/types";

const TYPES = [
  ["", "All"], ["open_mic_slot", "Open mic"], ["paid_gig", "Paid gigs"], ["audition", "Auditions"],
  ["band_slot", "Bands"], ["dj_slot", "DJ"], ["host_role", "Hosts"],
] as const;

export default function GigsPage() {
  const { hasRole } = useAuth();
  const [type, setType] = useState("");
  const [genre, setGenre] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [paid, setPaid] = useState(false);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [gigs, setGigs] = useState<Opportunity[] | null>(null);

  useEffect(() => { api<Genre[]>("/genres").then(setGenres).catch(() => {}); }, []);

  useEffect(() => {
    // Debounce typing so we don't fire a request per keystroke.
    const t = setTimeout(() => setQuery(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (type) params.set("type", type);
    if (genre) params.set("genre", genre);
    if (paid) params.set("compensation", "paid");
    if (query) params.set("q", query);
    setGigs(null);
    api<Page<Opportunity>>(`/opportunities?${params}`).then((p) => setGigs(p.results)).catch(() => setGigs([]));
  }, [type, genre, paid, query]);

  return (
    <>
      <TopBar title="Find gigs" right={hasRole("organizer") && (
        <Link href="/gigs/new" className="btn sm primary"><Icon name="plus" size={16} />Post</Link>
      )} />
      <div className="page">
        <div className="row card" style={{ padding: "0 12px", gap: 8 }}>
          <Icon name="search" size={18} />
          <input className="input" placeholder="Search open mics, auditions, venues…" value={q}
            onChange={(e) => setQ(e.target.value)} style={{ border: 0, background: "transparent", paddingLeft: 0 }}
            aria-label="Search gigs" />
        </div>
        <div className="chips" role="tablist" aria-label="Gig type">
          {TYPES.map(([key, text]) => (
            <button key={key} className={`chip ${type === key ? "on" : ""}`} onClick={() => setType(key)}>{text}</button>
          ))}
        </div>
        <div className="chips" aria-label="Genre">
          <button className={`chip ${paid ? "on" : ""}`} onClick={() => setPaid(!paid)}>💰 Paid only</button>
          {genres.map((g) => (
            <button key={g.slug} className={`chip ${genre === g.slug ? "on" : ""}`}
              onClick={() => setGenre(genre === g.slug ? "" : g.slug)}>#{g.name}</button>
          ))}
        </div>
        {gigs === null ? <Skeletons n={4} /> : gigs.length === 0 ? (
          <Empty icon="🎤" title="No open gigs match">Try another genre or clear filters.</Empty>
        ) : (
          <>
            <div className="small muted">{gigs.length} open {gigs.length === 1 ? "opportunity" : "opportunities"}</div>
            {gigs.map((g) => <GigCard key={g.id} gig={g} />)}
          </>
        )}
      </div>
    </>
  );
}

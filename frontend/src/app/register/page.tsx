"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TopBar } from "@/components/ui";
import { ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ROLES = [
  { key: "artist", title: "I perform", text: "Find gigs and apply with your portfolio" },
  { key: "organizer", title: "I host", text: "Post slots and book performers" },
] as const;

export default function RegisterPage() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const [roles, setRoles] = useState<string[]>(["artist"]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toggle = (r: string) => setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/auth/register", { ...form, roles });
      await refresh();
      router.replace("/me");
    } catch (err) {
      setError(err instanceof ApiError ? err.fieldMessage() ?? err.body.message : "Could not register.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar back />
      <form className="page" onSubmit={submit} style={{ gap: 14 }}>
        <h2 style={{ fontSize: 28, margin: "10px 0 0", letterSpacing: "-0.02em" }}>Join EQura</h2>
        <div className="col" style={{ gap: 8 }}>
          <span className="small muted bold">You can be both — pick all that apply</span>
          {ROLES.map((r) => (
            <button type="button" key={r.key} onClick={() => toggle(r.key)} className="card row"
              style={{ textAlign: "left", cursor: "pointer", borderColor: roles.includes(r.key) ? "var(--spot)" : undefined }}>
              <div className="grow">
                <div className="bold">{r.title}</div>
                <div className="small muted">{r.text}</div>
              </div>
              <span className="tag" style={roles.includes(r.key) ? { background: "var(--spot)", color: "#1a1206" } : {}}>
                {roles.includes(r.key) ? "Selected" : "Select"}
              </span>
            </button>
          ))}
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="field">
          <label htmlFor="name">Name or stage name</label>
          <input id="name" className="input" value={form.display_name} autoComplete="name"
            onChange={(e) => setForm({ ...form, display_name: e.target.value })} required maxLength={80} />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" className="input" type="email" autoComplete="email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        </div>
        <div className="field">
          <label htmlFor="pw">Password</label>
          <input id="pw" className="input" type="password" autoComplete="new-password" minLength={10}
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          <span className="tiny faint">At least 10 characters.</span>
        </div>
        <button className="btn primary block" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        <p className="muted small" style={{ textAlign: "center" }}>
          Already a member? <Link href="/login" style={{ color: "var(--spot)" }}>Sign in</Link>
        </p>
      </form>
    </>
  );
}

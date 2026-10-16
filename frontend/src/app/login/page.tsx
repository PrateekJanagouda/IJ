"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TopBar } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/feed");
    } catch (err) {
      setError(err instanceof ApiError ? err.body.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar back />
      <form className="page" onSubmit={submit} style={{ gap: 14 }}>
        <div>
          <h2 style={{ fontSize: 28, margin: "10px 0 4px", letterSpacing: "-0.02em" }}>Welcome back</h2>
          <p className="muted" style={{ margin: 0 }}>Every artist deserves a stage.</p>
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" className="input" type="email" autoComplete="email" inputMode="email"
            value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" className="input" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="btn primary block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="muted small" style={{ textAlign: "center" }}>
          New to EQura? <Link href="/register" style={{ color: "var(--spot)" }}>Create an account</Link>
        </p>
      </form>
    </>
  );
}

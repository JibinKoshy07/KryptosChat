"use client";

import { useState } from "react";

import { login } from "@/lib/api";

export function LoginForm({ onSuccess }: { onSuccess: (role: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await login(username, password);
      onSuccess(res.user.role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-deeper">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg bg-bg-panel p-8 shadow-2xl">
        <div className="mb-2 text-2xl font-semibold text-text-DEFAULT">Krypte</div>
        <p className="mb-6 text-sm text-text-muted">Private, self-hosted, encrypted chat.</p>

        <label className="block text-xs text-text-faint mb-1" htmlFor="username">Username</label>
        <input
          id="username"
          className="mb-3 w-full rounded-md border border-surface-DEFAULT bg-bg-panel px-3 py-2 text-text-DEFAULT"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <label className="block text-xs text-text-faint mb-1" htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          className="mb-4 w-full rounded-md border border-surface-DEFAULT bg-bg-panel px-3 py-2 text-text-DEFAULT"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <div className="mb-3 text-sm text-red-400">{error}</div>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-ac-DEFAULT py-2 font-medium text-white"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
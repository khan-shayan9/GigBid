"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, errorText, unwrap } from "@/lib/client";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const session = await unwrap(
        api.POST("/auth/login", {
          body: { username: String(form.get("username")), password: String(form.get("password")) },
        }),
      );
      router.replace(session.profile.persona ? "/inbox" : "/onboarding");
    } catch (failure) {
      setError(errorText(failure));
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h1>Sign in to GigBid</h1>
      <form onSubmit={submit} className="space-y-3">
        <label className="label">
          Username
          <input name="username" autoComplete="username" required className="field" />
        </label>
        <label className="label">
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="field"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </section>
  );
}

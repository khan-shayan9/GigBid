"use client";

import { useState } from "react";
import { useSession } from "@/components/AppShell";
import { api, errorText, unwrap, type Schemas } from "@/lib/client";

/** Persona, rates, saved searches, Connects budget and autonomy (onboarding and settings). */
export function ProfileForm({ submitLabel, onSaved }: { submitLabel: string; onSaved: () => void }) {
  const { session, refresh } = useSession();
  const profile = session.profile;
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body: Schemas["ProfileIn"] = {
      persona: String(form.get("persona")),
      hourly_floor_usd: Number(form.get("hourly_floor_usd")),
      weekly_connects_budget: Number(form.get("weekly_connects_budget")),
      saved_searches: String(form.get("saved_searches"))
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      autonomy: form.get("autonomy") === "auto_skip_low_fit" ? "auto_skip_low_fit" : "manual",
      agency: form.get("agency") === "on",
    };
    try {
      await unwrap(api.PUT("/profile", { body }));
      await refresh();
      setError(undefined);
      setSaved(true);
      onSaved();
    } catch (failure) {
      setError(errorText(failure));
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <fieldset>
        <legend className="label">Persona (your portfolio and marketplace account)</legend>
        <div className="mt-1 flex flex-wrap gap-3">
          {session.personas.map((persona) => (
            <label key={persona} className="flex items-center gap-1 text-sm">
              <input
                type="radio"
                name="persona"
                value={persona}
                required
                defaultChecked={profile.persona === persona}
              />
              {persona.replaceAll("_", " ")}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="label">
          Hourly floor (USD)
          <input
            name="hourly_floor_usd"
            type="number"
            min={0}
            max={1000}
            defaultValue={profile.hourly_floor_usd}
            className="field"
          />
        </label>
        <label className="label">
          Weekly Connects budget
          <input
            name="weekly_connects_budget"
            type="number"
            min={0}
            max={1000}
            defaultValue={profile.weekly_connects_budget}
            className="field"
          />
        </label>
      </div>
      <label className="label">
        Saved searches (one per line; empty means all open jobs)
        <textarea
          name="saved_searches"
          rows={3}
          defaultValue={profile.saved_searches.join("\n")}
          className="field"
        />
      </label>
      <label className="label">
        Autonomy
        <select name="autonomy" defaultValue={profile.autonomy} className="field">
          <option value="manual">Manual: I review every job</option>
          <option value="auto_skip_low_fit">Hide jobs GigBid recommends skipping</option>
        </select>
        <span className="mt-1 block text-xs font-normal text-slate-500">
          GigBid never sends a proposal or message, or spends Connects, without your approval.
        </span>
      </label>
      <label className="label flex items-start gap-2">
        <input type="checkbox" name="agency" defaultChecked={profile.agency ?? false} className="mt-1" />
        <span>
          Agency mode
          <span className="mt-1 block text-xs font-normal text-slate-500">
            Route each job to the team member ({session.personas.join(", ")}) whose portfolio fits it best.
          </span>
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm text-green-700">
          Saved.
        </p>
      )}
      <button type="submit" className="btn-primary">
        {submitLabel}
      </button>
    </form>
  );
}

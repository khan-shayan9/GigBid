"use client";

import { useState } from "react";
import { Connections, PortfolioUpload } from "@/components/Connections";
import { ProfileForm } from "@/components/ProfileForm";
import { Empty, ErrorState, Loading } from "@/components/States";
import { api, errorText, unwrap } from "@/lib/client";
import { useLoad } from "@/lib/hooks";

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1>Settings</h1>
      <section className="card" aria-labelledby="profile-h">
        <h2 id="profile-h">Autonomy, budgets and saved searches</h2>
        <ProfileForm submitLabel="Save settings" onSaved={() => undefined} />
      </section>
      <section className="card" aria-labelledby="accounts-h">
        <h2 id="accounts-h">Connected accounts</h2>
        <Connections />
      </section>
      <section className="card" aria-labelledby="portfolio-h">
        <h2 id="portfolio-h">Portfolio</h2>
        <PortfolioUpload />
      </section>
      <MemoryViewer />
    </div>
  );
}

function MemoryViewer() {
  const memory = useLoad(() => unwrap(api.GET("/memory")), "memory");
  const [error, setError] = useState<string>();
  const forget = async (kind: string, id: string) => {
    try {
      await unwrap(api.DELETE("/memory/{kind}/{item_id}", { params: { path: { kind, item_id: id } } }));
      memory.reload();
    } catch (failure) {
      setError(errorText(failure));
    }
  };
  return (
    <section className="card" aria-labelledby="memory-h">
      <h2 id="memory-h">What GigBid has learned</h2>
      <p className="mb-2 text-sm text-slate-600">
        Only repeated approved edits and marketplace outcomes become memory. Delete anything you do not want used.
      </p>
      {memory.loading && !memory.data ? (
        <Loading what="memory" />
      ) : memory.error ? (
        <ErrorState error={memory.error} retry={memory.reload} />
      ) : memory.data!.items.length === 0 ? (
        <Empty>Nothing learned yet.</Empty>
      ) : (
        <ul className="space-y-2">
          {memory.data!.items.map((item) => (
            <li key={`${item.kind}-${item.id}`} className="flex flex-wrap items-start justify-between gap-2 rounded border border-slate-100 p-2 text-sm">
              <span>
                <span className="mr-1 rounded bg-slate-100 px-1 text-xs">{item.kind}</span>
                {item.summary}
              </span>
              <button type="button" className="btn" onClick={() => forget(item.kind, item.id)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </section>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DecisionBadge, money, RiskBadge, RunStatus } from "@/components/Badges";
import { Empty, ErrorState, Loading } from "@/components/States";
import { api, errorText, unwrap } from "@/lib/client";
import { useLoad } from "@/lib/hooks";

type Filter = "all" | "bid" | "skip" | "new";

export default function InboxPage() {
  const router = useRouter();
  const inbox = useLoad(() => unwrap(api.GET("/jobs"), true), "inbox");
  const [text, setText] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [actionError, setActionError] = useState<string>();

  const analyse = async (jobId: string) => {
    try {
      await unwrap(api.POST("/jobs/{job_id}/analyse", { params: { path: { job_id: jobId } } }), true);
      router.push(`/jobs/${encodeURIComponent(jobId)}`);
    } catch (failure) {
      setActionError(errorText(failure));
    }
  };
  const skip = async (jobId: string) => {
    try {
      await unwrap(api.POST("/jobs/{job_id}/skip", { params: { path: { job_id: jobId } } }));
      inbox.reload();
    } catch (failure) {
      setActionError(errorText(failure));
    }
  };

  const items = (inbox.data?.items ?? []).filter(({ job, run }) => {
    const matches = `${job.title} ${job.skills.join(" ")}`.toLowerCase().includes(text.toLowerCase());
    const kind = run?.decision ?? "new";
    return matches && (filter === "all" || filter === kind);
  });

  return (
    <div>
      <h1>Job inbox</h1>
      <div className="mb-4 flex flex-wrap gap-3">
        <label className="label flex-1">
          Filter by text
          <input value={text} onChange={(e) => setText(e.target.value)} className="field" />
        </label>
        <label className="label">
          Show
          <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)} className="field">
            <option value="all">All jobs</option>
            <option value="bid">Recommended bids</option>
            <option value="skip">Recommended skips</option>
            <option value="new">Not analysed</option>
          </select>
        </label>
      </div>
      {actionError && (
        <p role="alert" className="mb-3 text-sm text-red-700">
          {actionError}
        </p>
      )}
      {inbox.loading && !inbox.data ? (
        <Loading what="jobs" />
      ) : inbox.error ? (
        <ErrorState error={inbox.error} retry={inbox.reload} />
      ) : items.length === 0 ? (
        <Empty>No jobs match. Change the filter or your saved searches in Settings.</Empty>
      ) : (
        <ul className="space-y-3" aria-label="Jobs">
          {items.map(({ job, run }) => (
            <li key={job.job_id} className="card" data-testid={`job-${job.job_id}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <Link href={`/jobs/${encodeURIComponent(job.job_id)}`} className="font-semibold text-indigo-700 hover:underline">
                    {job.title}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {job.skills.join(", ")} · {job.connects_cost ?? "?"} Connects ·{" "}
                    {new Date(job.posted_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {run?.fit_score != null && (
                    <span className="text-sm font-semibold">Fit {Math.round(run.fit_score * 100)}%</span>
                  )}
                  {run?.member && <span className="text-sm">As {run.member}</span>}
                  <RiskBadge score={run?.risk_score} flags={run?.risk_flags ?? []} />
                  <DecisionBadge decision={run?.decision} />
                  {run && <span className="text-sm">{money(run.price)}</span>}
                  {run && <RunStatus run={run} />}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link href={`/jobs/${encodeURIComponent(job.job_id)}`} className="btn">
                  Open
                </Link>
                {!run && (
                  <button type="button" className="btn-primary" onClick={() => analyse(job.job_id)}>
                    Analyse
                  </button>
                )}
                <button type="button" className="btn" onClick={() => skip(job.job_id)}>
                  Skip
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { RunStatus } from "@/components/Badges";
import { ErrorState, Loading } from "@/components/States";
import { api, errorText, unwrap } from "@/lib/client";
import { useRun } from "@/lib/hooks";

export default function RunViewerPage() {
  const threadId = decodeURIComponent(useParams<{ id: string }>().id);
  const { run, error, live, follow } = useRun(threadId);
  const [retryError, setRetryError] = useState<string>();

  if (error) return <ErrorState error={error} retry={follow} />;
  if (!run) return <Loading what="the run" />;

  const retry = async () => {
    try {
      await unwrap(api.POST("/runs/{thread_id}/retry", { params: { path: { thread_id: threadId } } }));
      follow();
    } catch (failure) {
      setRetryError(errorText(failure));
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="break-all">Run {threadId}</h1>
      <div className="card flex flex-wrap items-center gap-3 text-sm">
        <RunStatus run={run} />
        <span>{run.steps} steps</span>
        <span>{run.tokens_used} tokens</span>
        {run.kind === "bid" && run.draft && (
          <Link className="btn-quiet" href={`/studio/${encodeURIComponent(threadId)}`}>
            Proposal studio
          </Link>
        )}
        {run.trace_url ? (
          <a className="btn-quiet" href={run.trace_url} target="_blank" rel="noreferrer">
            Full trace (Langfuse)
          </a>
        ) : (
          <span className="text-slate-500">Full trace: tracing is off on this server.</span>
        )}
      </div>
      {run.errors.length > 0 && (
        <div role="alert" className="card border-red-200 bg-red-50 text-sm text-red-900">
          <ul className="list-disc pl-5">
            {run.errors.map((item) => <li key={item}>{item}</li>)}
          </ul>
          {!run.running && !run.pending_approval && (
            <button type="button" className="btn mt-2" onClick={retry}>
              Retry
            </button>
          )}
          {retryError && <p className="mt-1">{retryError}</p>}
        </div>
      )}
      {run.running && (
        <section className="card" aria-live="polite" aria-labelledby="live-h">
          <h2 id="live-h">Live</h2>
          <ol className="list-decimal pl-5 text-sm">
            {live.map((node, index) => <li key={`${node}-${index}`}>{node} finished</li>)}
            <li className="text-indigo-700">working…</li>
          </ol>
        </section>
      )}
      <section className="card" aria-labelledby="timeline-h">
        <h2 id="timeline-h">Timeline (from the checkpoint)</h2>
        <ol className="space-y-1 text-sm">
          {run.timeline.map((step) => (
            <li key={step.step} className="flex flex-wrap gap-2">
              <span className="w-16 text-slate-500">step {step.step}</span>
              <span className="font-medium">{step.nodes.join(" | ")}</span>
              {step.at && <span className="text-slate-500">{new Date(step.at).toLocaleTimeString()}</span>}
            </li>
          ))}
          {run.pending_approval && <li className="font-medium text-amber-700">paused: waiting for your approval</li>}
        </ol>
      </section>
    </div>
  );
}

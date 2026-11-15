import Link from "next/link";
import { RunStatus } from "@/components/Badges";
import type { Schemas } from "@/lib/client";

/** Live node-by-node progress while a run works, and why it stopped if it did. */
export function RunProgress({ run, live }: { run: Schemas["RunDetail"]; live: string[] }) {
  return (
    <div className="card space-y-2" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <RunStatus run={run} />
        <Link href={`/runs/${encodeURIComponent(run.thread_id)}`} className="btn-quiet">
          Run viewer
        </Link>
      </div>
      {run.running && (
        <p className="text-sm text-slate-600">
          {live.length ? `Finished: ${live.join(" → ")}` : "Starting the agents…"}
        </p>
      )}
      {run.errors.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-red-800">
          {run.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

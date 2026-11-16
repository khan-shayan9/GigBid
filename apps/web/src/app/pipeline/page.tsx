"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Empty, ErrorState, Loading } from "@/components/States";
import { api, unwrap, type Schemas } from "@/lib/client";
import { useLoad } from "@/lib/hooks";

const STAGES: [Schemas["PipelineCard"]["stage"], string][] = [
  ["awaiting_approval", "Awaiting approval"],
  ["drafted", "Drafted"],
  ["submitted", "Submitted"],
  ["viewed", "Viewed"],
  ["replied", "Replied"],
  ["interview", "Interview"],
  ["hired", "Hired"],
  ["lost", "Lost"],
];

export default function PipelinePage() {
  const board = useLoad(() => unwrap(api.GET("/pipeline"), true), "pipeline");
  const { reload } = board;
  // The board reloads when a run ends or the worker sees a new proposal outcome.
  useEffect(() => {
    const source = new EventSource("/api/pipeline/stream");
    source.addEventListener("changed", () => reload());
    return () => source.close();
  }, [reload]);
  if (board.loading && !board.data) return <Loading what="the pipeline" />;
  if (board.error) return <ErrorState error={board.error} retry={board.reload} />;
  const cards = board.data!.cards;
  return (
    <div>
      <div className="flex items-center justify-between">
        <h1>Pipeline</h1>
        <button type="button" className="btn" onClick={board.reload}>
          Refresh
        </button>
      </div>
      {cards.length === 0 ? (
        <Empty>No proposals yet. Analyse a job in the inbox to start.</Empty>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STAGES.map(([stage, label]) => {
            const column = cards.filter((card) => card.stage === stage);
            return (
              <section key={stage} aria-label={label} className="w-56 shrink-0 rounded-lg bg-slate-100 p-2">
                <h2 className="text-sm">
                  {label} <span className="text-slate-500">({column.length})</span>
                </h2>
                <ul className="space-y-2">
                  {column.map((card) => (
                    <li key={`${card.stage}-${card.job_id}`} className="card p-2 text-sm">
                      {card.thread_id ? (
                        <Link href={`/studio/${encodeURIComponent(card.thread_id)}`} className="text-indigo-700 hover:underline">
                          {card.title}
                        </Link>
                      ) : (
                        card.title
                      )}
                      {card.proposal && (
                        <p className="text-xs text-slate-500">
                          ${card.proposal.bid.amount_usd} · {card.proposal.connects_cost} Connects
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

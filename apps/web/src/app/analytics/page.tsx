"use client";

import { ErrorState, Loading } from "@/components/States";
import { api, unwrap } from "@/lib/client";
import { useLoad } from "@/lib/hooks";

function Counts({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  return (
    <section className="card" aria-label={title}>
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">Nothing yet.</p>
      ) : (
        <dl className="grid grid-cols-[1fr_auto] gap-1 text-sm">
          {entries.map(([name, count]) => (
            <div key={name} className="contents">
              <dt>{name.replaceAll("_", " ")}</dt>
              <dd className="text-right font-semibold">{count}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

const seconds = (value: number | null | undefined) => (value == null ? "none yet" : `${value.toFixed(1)} s`);

export default function AnalyticsPage() {
  const stats = useLoad(() => unwrap(api.GET("/analytics"), true), "analytics");
  if (stats.loading && !stats.data) return <Loading what="analytics" />;
  if (stats.error) return <ErrorState error={stats.error} retry={stats.reload} />;
  const data = stats.data!;
  const cost = data.cost_and_latency;
  return (
    <div className="space-y-4">
      <h1>Analytics</h1>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card"><p className="text-sm">Jobs analysed</p><p className="text-2xl font-bold">{data.jobs_analysed}</p></div>
        <div className="card"><p className="text-sm">Connects spent</p><p className="text-2xl font-bold">{data.connects_spent}</p></div>
        <div className="card"><p className="text-sm">Runs needing attention</p><p className="text-2xl font-bold">{data.needs_attention}</p></div>
      </div>
      <section className="card overflow-x-auto" aria-labelledby="rates-h">
        <h2 id="rates-h">Reply and hire rate by category</h2>
        {data.rates_by_category.length === 0 ? (
          <p className="text-sm text-slate-500">No submitted proposals yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead><tr><th scope="col">Category (first skill)</th><th scope="col">Submitted</th><th scope="col">Reply rate</th><th scope="col">Hire rate</th></tr></thead>
            <tbody>
              {data.rates_by_category.map((row) => (
                <tr key={row.category} className="border-t border-slate-100">
                  <td>{row.category}</td>
                  <td>{row.submitted}</td>
                  <td>{Math.round((100 * row.replied) / row.submitted)}%</td>
                  <td>{Math.round((100 * row.hired) / row.submitted)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        <Counts title="Decisions" counts={data.decisions} />
        <Counts title="Approvals" counts={data.approvals} />
        <Counts title="Outcomes (marketplace)" counts={data.outcomes} />
      </div>
      <section className="card" aria-labelledby="reasons-h">
        <h2 id="reasons-h">Top rejection reasons</h2>
        {data.top_rejection_reasons.length === 0 ? (
          <p className="text-sm text-slate-500">No rejections yet.</p>
        ) : (
          <ol className="list-decimal pl-5 text-sm">
            {data.top_rejection_reasons.map((row) => <li key={row.reason}>{row.reason} ({row.count})</li>)}
          </ol>
        )}
      </section>
      <section className="card" aria-labelledby="cost-h">
        <h2 id="cost-h">Cost and latency</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="font-medium">p95 per job analysed</dt>
          <dd>{seconds(cost.p95_seconds_per_job)} ({cost.jobs_timed} jobs)</dd>
          <dt className="font-medium">p95 per proposal drafted</dt>
          <dd>{seconds(cost.p95_seconds_per_proposal)} ({cost.proposals_timed} proposals)</dd>
          <dt className="font-medium">p95 tokens per proposal</dt>
          <dd>{cost.p95_tokens_per_proposal ?? "none yet"}</dd>
        </dl>
        <p className="mt-1 text-xs text-slate-500">
          Measured from your runs&apos; checkpoints. Cost in USD per node is in each run&apos;s Langfuse trace.
        </p>
      </section>
    </div>
  );
}

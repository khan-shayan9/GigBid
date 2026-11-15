"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/components/AppShell";
import { DecisionBadge, money, RiskBadge } from "@/components/Badges";
import { RunProgress } from "@/components/RunProgress";
import { ErrorState, Loading } from "@/components/States";
import { api, ApiFailure, errorText, unwrap } from "@/lib/client";
import { useRun } from "@/lib/hooks";

export default function JobDetailPage() {
  const jobId = decodeURIComponent(useParams<{ id: string }>().id);
  const { session } = useSession();
  const { run, error, live, follow } = useRun(`${session.account}:bid:${jobId}`);
  const [startError, setStartError] = useState<string>();

  const analyse = async () => {
    try {
      await unwrap(api.POST("/jobs/{job_id}/analyse", { params: { path: { job_id: jobId } } }), true);
      follow();
    } catch (failure) {
      setStartError(errorText(failure));
    }
  };

  if (error instanceof ApiFailure && (error.status === 404 || error.code === "run_failed")) {
    return (
      <div>
        <h1>Job {jobId}</h1>
        {error.code === "run_failed" ? (
          <p role="alert" className="mb-3 text-red-700">{error.message}</p>
        ) : (
          <p className="mb-3 text-slate-600">GigBid has not analysed this job yet.</p>
        )}
        <button type="button" className="btn-primary" onClick={analyse}>
          {error.code === "run_failed" ? "Analyse again" : "Analyse"}
        </button>
        {startError && <p role="alert" className="mt-2 text-sm text-red-700">{startError}</p>}
      </div>
    );
  }
  if (error) return <ErrorState error={error} retry={follow} />;
  if (!run) return <Loading what="the job" />;

  const { job, job_spec: spec, risk_report: risk, fit_report: fit, decision, price_quote: price } = run;
  return (
    <div className="space-y-4">
      <h1>{job?.title ?? jobId}</h1>
      <RunProgress run={run} live={live} />
      {run.draft && (
        <Link href={`/studio/${encodeURIComponent(run.thread_id)}`} className="btn-primary">
          {run.pending_approval ? "Review the proposal" : "Open the proposal"}
        </Link>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <section className="card" aria-labelledby="decision-h">
          <h2 id="decision-h">Bid or skip</h2>
          <DecisionBadge decision={decision?.decision} />
          <ul className="mt-2 list-disc pl-5 text-sm">
            {(decision?.reasons ?? []).map((reason) => <li key={reason}>{reason}</li>)}
            {decision?.decision === "bid" && <li>Fit and risk are within your thresholds.</li>}
          </ul>
        </section>
        <section className="card" aria-labelledby="risk-h">
          <h2 id="risk-h">Risk report</h2>
          {risk ? (
            <>
              <RiskBadge score={risk.score} flags={risk.flags ?? []} />
              <p className="mt-2 text-sm">Score {risk.score.toFixed(2)}. {risk.explanation}</p>
            </>
          ) : (
            <p className="text-sm text-slate-500">Not assessed yet.</p>
          )}
        </section>
        <section className="card" aria-labelledby="spec-h">
          <h2 id="spec-h">Job spec</h2>
          {spec ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="font-medium">Skills</dt>
              <dd>{(spec.required_skills ?? []).join(", ") || "—"}</dd>
              <dt className="font-medium">Deliverables</dt>
              <dd>{(spec.deliverables ?? []).join("; ") || "—"}</dd>
              <dt className="font-medium">Budget</dt>
              <dd>
                {spec.budget_min ?? "?"} – {spec.budget_max ?? "?"} USD
              </dd>
              <dt className="font-medium">Connects</dt>
              <dd>{job?.connects_cost ?? "?"}</dd>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Not extracted yet.</p>
          )}
          {job && <p className="mt-2 whitespace-pre-line text-sm text-slate-700">{job.description}</p>}
        </section>
        <section className="card" aria-labelledby="price-h">
          <h2 id="price-h">Price</h2>
          {price ? (
            <>
              <p className="font-semibold">{money(price)}</p>
              <p className="text-sm">{price.rationale}</p>
            </>
          ) : (
            <p className="text-sm text-slate-500">
              {decision?.decision === "skip" ? "No price: GigBid recommends skipping." : "Not priced yet."}
            </p>
          )}
        </section>
      </div>
      <section className="card overflow-x-auto" aria-labelledby="matrix-h">
        <h2 id="matrix-h">Requirements and evidence {fit && `(fit ${Math.round(fit.score * 100)}%)`}</h2>
        {fit && (fit.matrix ?? []).length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <th scope="col" className="py-1 pr-3">Requirement</th>
                <th scope="col" className="py-1 pr-3">Covered</th>
                <th scope="col" className="py-1 pr-3">Best score</th>
                <th scope="col" className="py-1">Portfolio items</th>
              </tr>
            </thead>
            <tbody>
              {(fit.matrix ?? []).map((row) => (
                <tr key={row.requirement} className="border-t border-slate-100">
                  <td className="py-1 pr-3">{row.requirement}</td>
                  <td className="py-1 pr-3">{row.covered ? "Yes" : "No"}</td>
                  <td className="py-1 pr-3">{row.best_score.toFixed(2)}</td>
                  <td className="py-1">{(row.evidence_ids ?? []).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-500">No evidence matched yet.</p>
        )}
      </section>
    </div>
  );
}

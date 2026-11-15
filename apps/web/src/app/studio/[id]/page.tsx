"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { money } from "@/components/Badges";
import { CitedText } from "@/components/EvidenceHover";
import { RunProgress } from "@/components/RunProgress";
import { Empty, ErrorState, Loading } from "@/components/States";
import { api, errorText, unwrap, type Schemas } from "@/lib/client";
import { useRun } from "@/lib/hooks";

const LABEL_STYLE: Record<string, string> = {
  supported: "bg-green-100 text-green-800",
  partly_supported: "bg-amber-100 text-amber-800",
  unsupported: "bg-red-100 text-red-800",
};

export default function StudioPage() {
  const threadId = decodeURIComponent(useParams<{ id: string }>().id);
  const { run, error, live, follow } = useRun(threadId);
  const [text, setText] = useState("");
  const original = run?.draft?.cover_letter ?? "";
  useEffect(() => setText(original), [original]);

  if (error) return <ErrorState error={error} retry={follow} />;
  if (!run) return <Loading what="the proposal" />;
  if (!run.draft) {
    return (
      <div>
        <h1>Proposal studio</h1>
        <RunProgress run={run} live={live} />
        <Empty>No draft yet. Drafts appear here when GigBid recommends bidding.</Empty>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="break-words">Proposal: {run.job?.title}</h1>
      <RunProgress run={run} live={live} />
      <Outcome run={run} />
      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-4">
          <section className="card" aria-labelledby="draft-h">
            <h2 id="draft-h">Draft with evidence</h2>
            <p className="mb-2 text-xs text-slate-500">Hover or focus a citation to see the portfolio item behind it.</p>
            <Paragraphs text={text} setText={setText} run={run} editable={run.pending_approval} />
          </section>
          {run.pending_approval && (
            <section className="card">
              <label className="label">
                Edit the cover letter
                <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} maxLength={5000} className="field font-mono" />
              </label>
            </section>
          )}
        </div>
        <div className="space-y-4">
          <Review run={run} />
          <Preview run={run} />
          {run.pending_approval && (
            <ApprovalPanel threadId={threadId} field="cover_letter" original={original} edited={text} onResumed={follow} />
          )}
        </div>
      </div>
    </div>
  );
}

function Paragraphs({ text, setText, run, editable }: { text: string; setText: (value: string) => void; run: Schemas["RunDetail"]; editable: boolean }) {
  const [busy, setBusy] = useState<number>();
  const [error, setError] = useState<string>();
  const paragraphs = text.split(/\n\s*\n/);
  const regenerate = async (index: number) => {
    setBusy(index);
    try {
      const { paragraph } = await unwrap(
        api.POST("/runs/{thread_id}/regenerate", {
          params: { path: { thread_id: run.thread_id } },
          body: { paragraph: paragraphs[index] },
        }),
      );
      setText(paragraphs.map((old, at) => (at === index ? paragraph : old)).join("\n\n"));
      setError(undefined);
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(undefined);
    }
  };
  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, index) => (
        <div key={index} className="rounded border border-slate-100 p-2">
          <p className="text-sm leading-6">
            <CitedText text={paragraph} evidence={run.evidence} />
          </p>
          {editable && (
            <button type="button" className="btn-quiet mt-1" disabled={busy !== undefined} onClick={() => regenerate(index)}>
              {busy === index ? "Rewriting…" : "Regenerate this paragraph"}
            </button>
          )}
        </div>
      ))}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </div>
  );
}

function Review({ run }: { run: Schemas["RunDetail"] }) {
  return (
    <section className="card space-y-3" aria-labelledby="review-h">
      <h2 id="review-h">Checks</h2>
      <div>
        <h3 className="text-sm font-semibold">Critic {run.critique?.passed ? "✓ passed" : "✗ asked for changes"}</h3>
        <p className="text-xs text-slate-500">Revisions: {run.revisions}</p>
        <ul className="list-disc pl-5 text-sm">
          {(run.critique?.reasons ?? []).map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      </div>
      <div>
        <h3 className="text-sm font-semibold">Compliance {run.compliance?.allowed ? "✓ allowed" : "✗ blocked"}</h3>
        <ul className="list-disc pl-5 text-sm">
          {(run.compliance?.violations ?? []).map((violation) => <li key={violation}>{violation}</li>)}
        </ul>
      </div>
      <div>
        <h3 className="text-sm font-semibold">Claim check</h3>
        {run.claims.length === 0 ? (
          <p className="text-sm text-slate-500">No experience claims to check.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {run.claims.map((claim) => (
              <li key={`${claim.sentence}-${claim.claim}`}>
                <span className={`mr-1 rounded px-1 text-xs ${LABEL_STYLE[claim.label] ?? ""}`}>{claim.label.replace("_", " ")}</span>
                {claim.claim}
                {claim.label === "unsupported" && <span className="text-xs text-slate-500"> (removed)</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function Preview({ run }: { run: Schemas["RunDetail"] }) {
  const proposal = run.preview?.proposal;
  return (
    <section className="card" aria-labelledby="preview-h">
      <h2 id="preview-h">What will be sent (dry run)</h2>
      {proposal ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="font-medium">Bid</dt>
          <dd>{money({ bid_type: proposal.bid.type, amount_usd: proposal.bid.amount_usd, rationale: "" })}</dd>
          <dt className="font-medium">Connects cost</dt>
          <dd>{proposal.connects_cost}</dd>
          <dt className="font-medium">Price rationale</dt>
          <dd>{run.price_quote?.rationale}</dd>
        </dl>
      ) : (
        <p className="text-sm text-slate-500">{run.preview?.unavailable ?? "No preview yet."}</p>
      )}
    </section>
  );
}

function Outcome({ run }: { run: Schemas["RunDetail"] }) {
  if (run.running || run.pending_approval || !run.approval_status) return null;
  const submitted = run.submission;
  return (
    <div role="status" className="card border-indigo-200 bg-indigo-50 text-sm">
      {run.approval_status === "approved" && submitted
        ? `Submitted. ${submitted.connects_cost} Connects spent; ${submitted.balance_after} left.`
        : run.approval_status === "blocked_after_edit"
          ? `Your edit was blocked by the compliance check: ${(run.compliance?.violations ?? []).join(", ")}. Nothing was sent.`
          : run.approval_status.startsWith("rejected")
            ? `Rejected. Nothing was sent. ${run.approval_status.replace(/^rejected:?\s*/, "") ? `Reason: ${run.approval_status.replace(/^rejected:?\s*/, "")}` : ""}`
            : `Status: ${run.approval_status}`}
    </div>
  );
}

"use client";

import { useState } from "react";
import { api, errorText, unwrap } from "@/lib/client";

type Props = {
  threadId: string;
  field: "cover_letter" | "reply";
  original: string;
  edited: string;
  onResumed: () => void;
};

/** Approve, approve with edits, or reject with a reason. Each one resumes the paused graph. */
export function ApprovalPanel({ threadId, field, original, edited, onResumed }: Props) {
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const changed = edited.trim() !== original.trim();

  const resume = async (body: { action: "approve" | "edit" | "reject"; reason?: string } & Partial<Record<Props["field"], string>>) => {
    setBusy(true);
    try {
      await unwrap(api.POST("/runs/{thread_id}/resume", { params: { path: { thread_id: threadId } }, body }));
      setError(undefined);
      onResumed();
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card space-y-3" aria-labelledby="approval-h">
      <h2 id="approval-h">Your decision</h2>
      <p className="text-sm text-slate-600">
        Nothing is sent until you approve. {changed && "Your edits are checked against the platform policy again."}
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn-primary"
          disabled={busy || !edited.trim()}
          onClick={() => resume(changed ? { action: "edit", [field]: edited } : { action: "approve" })}
        >
          {changed ? "Approve with my edits" : "Approve and send"}
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => setRejecting((open) => !open)} aria-expanded={rejecting}>
          Reject…
        </button>
      </div>
      {rejecting && (
        <div className="space-y-2">
          <label className="label">
            Reason (helps GigBid learn)
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} rows={2} className="field" />
          </label>
          <button type="button" className="btn-danger" disabled={busy} onClick={() => resume({ action: "reject", reason: reason.trim() || undefined })}>
            Confirm rejection
          </button>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { RunStatus } from "@/components/Badges";
import { Empty, ErrorState, Loading } from "@/components/States";
import { api, errorText, unwrap, type Schemas } from "@/lib/client";
import { useLoad, useRun } from "@/lib/hooks";

export default function MessagesPage() {
  const inbox = useLoad(() => unwrap(api.GET("/messages"), true), "messages");
  if (inbox.loading && !inbox.data) return <Loading what="messages" />;
  if (inbox.error) return <ErrorState error={inbox.error} retry={inbox.reload} />;
  const threads = inbox.data!.threads;
  return (
    <div className="space-y-4">
      <h1>Messages</h1>
      {threads.length === 0 ? (
        <Empty>No client messages yet.</Empty>
      ) : (
        threads.map((thread) => <Thread key={thread.thread_id} thread={thread} onSent={inbox.reload} />)
      )}
    </div>
  );
}

function Thread({ thread, onSent }: { thread: Schemas["MessageThread"]; onSent: () => void }) {
  const [runId, setRunId] = useState(thread.reply_run?.thread_id ?? null);
  const [error, setError] = useState<string>();
  const latest = thread.latest_client_message_id;

  const suggest = async () => {
    try {
      const ref = await unwrap(api.POST("/messages/{message_id}/reply", { params: { path: { message_id: latest! } } }), true);
      setRunId(ref.thread_id);
    } catch (failure) {
      setError(errorText(failure));
    }
  };

  return (
    <section className="card space-y-3" aria-label={`Conversation about job ${thread.job_id}`}>
      <h2>Job {thread.job_id}</h2>
      <ol className="space-y-2">
        {thread.messages.map((message) => (
          <li
            key={message.message_id}
            className={`max-w-prose rounded p-2 text-sm ${message.sender === "client" ? "bg-slate-100" : "ml-auto bg-indigo-50"}`}
          >
            <span className="block text-xs text-slate-500">
              {message.sender} · {new Date(message.sent_at).toLocaleString()}
            </span>
            {message.text}
          </li>
        ))}
      </ol>
      {runId ? (
        <Reply threadId={runId} onSent={onSent} />
      ) : (
        latest && (
          <button type="button" className="btn-primary" onClick={suggest}>
            Suggest a reply
          </button>
        )
      )}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </section>
  );
}

function Reply({ threadId, onSent }: { threadId: string; onSent: () => void }) {
  const { run, error, follow } = useRun(threadId);
  const [text, setText] = useState("");
  const original = run?.reply ?? "";
  useEffect(() => setText(original), [original]);
  const sent = run?.approval_status === "approved" && !run.running;
  useEffect(() => {
    if (sent) onSent();
  }, [sent, onSent]);

  if (error) return <ErrorState error={error} retry={follow} />;
  if (!run || run.running) return <Loading what="the suggested reply" />;
  if (run.intent === "scam_signal") {
    return <p role="alert" className="text-sm text-red-800">This message looks like a scam (off-platform or payment request). GigBid did not draft a reply.</p>;
  }
  return (
    <div className="space-y-3 border-t border-slate-100 pt-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>Intent: <strong>{run.intent?.replaceAll("_", " ")}</strong></span>
        <RunStatus run={run} />
      </div>
      {run.slots.length > 0 && (
        <div className="text-sm">
          Interview slots offered:
          <ul className="list-disc pl-5">
            {run.slots.map((slot) => <li key={slot.start}>{new Date(slot.start).toLocaleString()} – {new Date(slot.end).toLocaleTimeString()}</li>)}
          </ul>
        </div>
      )}
      {run.compliance && !run.compliance.allowed && (
        <p role="alert" className="text-sm text-red-800">Blocked by the compliance check: {(run.compliance.violations ?? []).join(", ")}</p>
      )}
      {run.pending_approval ? (
        <>
          <label className="label">
            Suggested reply
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={3000} className="field" />
          </label>
          <ApprovalPanel threadId={threadId} field="reply" original={original} edited={text} onResumed={follow} />
        </>
      ) : (
        run.approval_status && <p role="status" className="text-sm">Reply {run.approval_status}.</p>
      )}
    </div>
  );
}

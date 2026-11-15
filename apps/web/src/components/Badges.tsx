import type { Schemas } from "@/lib/client";

export function RiskBadge({ score, flags }: { score?: number | null; flags: string[] }) {
  if (score === undefined || score === null) return null;
  const level = score > 0.7 ? "high" : score > 0.3 ? "medium" : "low";
  const colours = {
    high: "bg-red-100 text-red-800",
    medium: "bg-amber-100 text-amber-800",
    low: "bg-green-100 text-green-800",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${colours[level]}`}
      title={flags.join(", ") || "no risk flags"}
    >
      Risk {level}
      {flags.length > 0 && `: ${flags.join(", ").replaceAll("_", " ")}`}
    </span>
  );
}

export function DecisionBadge({ decision }: { decision?: string | null }) {
  if (!decision) return <span className="text-xs text-slate-500">Not analysed</span>;
  const bid = decision === "bid";
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-semibold ${bid ? "bg-indigo-100 text-indigo-800" : "bg-slate-200 text-slate-700"}`}
    >
      Recommended: {decision}
    </span>
  );
}

export function RunStatus({ run }: { run: Pick<Schemas["RunSummary"], "running" | "pending_approval" | "status" | "approval_status"> }) {
  if (run.status) {
    return (
      <span role="status" className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
        {run.status === "dead_letter" ? "Failed (dead letter)" : "Needs attention"}
      </span>
    );
  }
  if (run.running) return <span className="text-xs text-indigo-700">Working…</span>;
  if (run.pending_approval) {
    return <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">Awaiting your approval</span>;
  }
  if (run.approval_status) return <span className="text-xs text-slate-600">{run.approval_status}</span>;
  return null;
}

export function money(price?: Schemas["PriceQuote"] | null): string {
  if (!price) return "—";
  return price.bid_type === "hourly" ? `$${price.amount_usd}/h` : `$${price.amount_usd} fixed`;
}

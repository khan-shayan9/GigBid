"use client";

import { useEffect, useState } from "react";
import { DEGRADED_EVENT } from "@/lib/client";

/** Shown while the marketplace is unavailable; cleared by the next call that reaches it. */
export function DegradedBanner() {
  const [degraded, setDegraded] = useState(false);
  useEffect(() => {
    const update = (event: Event) => setDegraded(Boolean((event as CustomEvent).detail));
    window.addEventListener(DEGRADED_EVENT, update);
    return () => window.removeEventListener(DEGRADED_EVENT, update);
  }, []);
  if (!degraded) return null;
  return (
    <div role="alert" className="border-b border-amber-300 bg-amber-50">
      <p className="mx-auto max-w-6xl px-4 py-2 text-sm text-amber-900">
        <strong>Marketplace unavailable.</strong> Your drafts and approvals are kept. GigBid will
        work again when the marketplace is back; try again in a moment.
      </p>
    </div>
  );
}

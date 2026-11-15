import { Fragment } from "react";
import type { Schemas } from "@/lib/client";

const CITATION = /\[([A-Za-z0-9_-]+)\]/g;

/** Text with every [evidence-id] citation shown as a chip that reveals its evidence on hover or focus. */
export function CitedText({ text, evidence }: { text: string; evidence: Schemas["EvidenceItem"][] }) {
  const byId = new Map(evidence.map((item) => [item.id, item]));
  const parts = text.split(CITATION); // odd indexes are the cited ids
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 0 ? (
          <Fragment key={index}>{part}</Fragment>
        ) : (
          <EvidenceHover key={index} id={part} item={byId.get(part)} />
        ),
      )}
    </>
  );
}

function EvidenceHover({ id, item }: { id: string; item?: Schemas["EvidenceItem"] }) {
  return (
    <span className="group relative inline-block">
      <button
        type="button"
        className={`mx-0.5 rounded px-1 text-xs font-medium ${item ? "bg-indigo-100 text-indigo-800" : "bg-red-100 text-red-800"}`}
        aria-describedby={`evidence-${id}`}
      >
        {id}
      </button>
      <span
        role="tooltip"
        id={`evidence-${id}`}
        className="absolute left-0 top-full z-10 mt-1 hidden w-72 max-w-[80vw] rounded border border-slate-200 bg-white p-2 text-xs text-slate-800 shadow-lg group-focus-within:block group-hover:block"
      >
        {item ? (
          <>
            <strong>{item.title}</strong> ({item.type.replaceAll("_", " ")})
            <span className="mt-1 block">{item.text.slice(0, 400)}</span>
          </>
        ) : (
          "No evidence with this id: this claim is not supported."
        )}
      </span>
    </span>
  );
}

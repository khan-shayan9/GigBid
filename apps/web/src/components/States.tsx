import { errorText } from "@/lib/client";

export function Loading({ what }: { what: string }) {
  return (
    <p role="status" aria-live="polite" className="py-8 text-center text-slate-500">
      Loading {what}…
    </p>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="my-4 rounded border border-red-300 bg-red-50 p-4 text-red-900">
      <p>{errorText(error)}</p>
      {retry && (
        <button type="button" onClick={retry} className="btn mt-2">
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 rounded border border-dashed border-slate-300 p-6 text-center text-slate-600">
      {children}
    </div>
  );
}

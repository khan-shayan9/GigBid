// The typed API client. Types come from the generated src/lib/api/schema.d.ts (FastAPI OpenAPI).
import createClient from "openapi-fetch";
import type { components, paths } from "@/lib/api/schema";

export type Schemas = components["schemas"];
export const api = createClient<paths>({ baseUrl: "/api" });

export const DEGRADED_EVENT = "gigbid:degraded";
export const SIGNED_OUT_EVENT = "gigbid:signed-out";

export class ApiFailure extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** The response body, or an ApiFailure with the API's stable error code. */
export async function unwrap<T>(call: Promise<Result<T>>, touchesMarketplace = false): Promise<T> {
  const { data, error, response } = await call;
  if (response.ok) {
    if (touchesMarketplace) window.dispatchEvent(new CustomEvent(DEGRADED_EVENT, { detail: false }));
    return data as T;
  }
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  const known = typeof detail === "object" && detail !== null && "code" in detail;
  const code = known ? String((detail as { code: string }).code) : `http_${response.status}`;
  const message = known
    ? String((detail as { message?: string }).message ?? code)
    : "The request was not accepted. Check the fields and try again.";
  if (code === "marketplace_unavailable") {
    window.dispatchEvent(new CustomEvent(DEGRADED_EVENT, { detail: true }));
  }
  if (response.status === 401) window.dispatchEvent(new CustomEvent(SIGNED_OUT_EVENT));
  throw new ApiFailure(response.status, code, message);
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

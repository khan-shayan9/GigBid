"use client";

import { useState } from "react";
import { ErrorState, Loading } from "@/components/States";
import { api, errorText, unwrap } from "@/lib/client";
import { useLoad } from "@/lib/hooks";

/** Marketplace connection status and the portfolio upload (onboarding and settings). */
export function Connections() {
  const status = useLoad(() => unwrap(api.GET("/profile/connections"), true), "connections");
  if (status.loading && !status.data) return <Loading what="connections" />;
  if (status.error) return <ErrorState error={status.error} retry={status.reload} />;
  const data = status.data!;
  return (
    <ul className="space-y-1 text-sm">
      <li>
        Mode: <strong>{data.marketplace_mode}</strong>
      </li>
      <li>
        GigSim:{" "}
        {data.marketplace ? (
          <span className="text-green-700">connected · {data.connects_balance} Connects</span>
        ) : (
          <span className="text-amber-700">unavailable</span>
        )}
      </li>
      <li>
        Upwork (live mode):{" "}
        {data.upwork_connected ? (
          "signed in"
        ) : (
          <span className="text-slate-600">
            not connected. Sign in once with{" "}
            <code>python -m mcp_servers.marketplace.adapters.upwork_live login</code>.
          </span>
        )}
      </li>
    </ul>
  );
}

export function PortfolioUpload() {
  const [message, setMessage] = useState<{ ok: boolean; text: string }>();
  const upload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    try {
      const saved = await unwrap(
        api.POST("/profile/portfolio", {
          // openapi-fetch sends FormData as is; the type expects the schema's field shape.
          body: body as unknown as { file: string },
          bodySerializer: (value) => value as unknown as FormData,
        }),
      );
      setMessage({ ok: true, text: `Saved as ${saved.saved_as}.` });
    } catch (failure) {
      setMessage({ ok: false, text: errorText(failure) });
    }
  };
  return (
    <form onSubmit={upload} className="space-y-2">
      <label className="label">
        Add to your portfolio (PDF CV, or Markdown and code files; kept in your account only)
        <input name="file" type="file" accept=".pdf,.md,.py,.ts,.js,.sql" className="field" />
      </label>
      <button type="submit" className="btn">
        Upload
      </button>
      {message && (
        <p role={message.ok ? "status" : "alert"} className={message.ok ? "text-sm text-green-700" : "text-sm text-red-700"}>
          {message.text}
        </p>
      )}
    </form>
  );
}

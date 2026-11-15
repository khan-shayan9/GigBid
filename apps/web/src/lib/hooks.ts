"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, unwrap, type Schemas } from "@/lib/client";

export type Load<T> = { data?: T; error?: unknown; loading: boolean; reload: () => void };

/** Load data once per `key`, with loading and error states and a reload. */
export function useLoad<T>(load: () => Promise<T>, key: string): Load<T> {
  const [state, setState] = useState<{ data?: T; error?: unknown; loading: boolean }>({
    loading: true,
  });
  const [round, setRound] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    let live = true;
    setState((old) => ({ data: old.data, loading: true }));
    loadRef.current().then(
      (data) => live && setState({ data, loading: false }),
      (error: unknown) => live && setState({ error, loading: false }),
    );
    return () => {
      live = false;
    };
  }, [key, round]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { ...state, reload };
}

export type RunView = {
  run?: Schemas["RunDetail"];
  error?: unknown;
  live: string[];
  /** Re-open the stream, e.g. after approving resumes the thread. */
  follow: () => void;
};

/** A run as the checkpoint has it, kept current by the server's SSE stream of graph updates. */
export function useRun(threadId: string | null): RunView {
  const [run, setRun] = useState<Schemas["RunDetail"]>();
  const [error, setError] = useState<unknown>();
  const [live, setLive] = useState<string[]>([]);
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!threadId) return;
    const fetchDetail = () =>
      unwrap(api.GET("/runs/{thread_id}", { params: { path: { thread_id: threadId } } })).then(
        (detail) => {
          setRun(detail);
          setError(undefined);
        },
        setError,
      );
    const source = new EventSource(`/api/runs/${encodeURIComponent(threadId)}/stream`);
    let gotSnapshot = false;
    source.addEventListener("snapshot", (event) => {
      gotSnapshot = true;
      setRun(JSON.parse((event as MessageEvent).data));
      setError(undefined);
    });
    source.addEventListener("node", (event) => {
      const { node } = JSON.parse((event as MessageEvent).data) as { node: string };
      setLive((nodes) => [...nodes, node]);
    });
    source.addEventListener("end", () => {
      source.close();
      void fetchDetail();
    });
    source.onerror = () => {
      source.close();
      if (!gotSnapshot) void fetchDetail(); // shows the API's real error (404, 403, ...)
    };
    return () => source.close();
  }, [threadId, round]);

  const follow = useCallback(() => {
    setLive([]);
    setRound((value) => value + 1);
  }, []);
  return { run, error, live, follow };
}

// A Run's progress as it happens: the API pushes each change (GET /api/runs/{id}/live, server-sent
// events, woken by Postgres) and this hands every message to `onDetail`. Where the stream cannot be had —
// no EventSource, or a proxy that refuses it — it asks every 2.5 s instead, as the pages used to.
import { useEffect, useRef } from "react";

import { api, BASE, call, type Schemas } from "@/api/client";

type Detail = Schemas["RunDetail"];

const POLL_MS = 2500;
const FINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

export function useRunLive(runId: string, live: boolean, onDetail: (d: Detail) => void) {
  // The newest callback, so a message is read against the page as it is now.
  const handler = useRef(onDetail);
  handler.current = onDetail;
  // The last event id seen: a fallback poll starts there.
  const after = useRef(0);

  useEffect(() => {
    if (!live) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const take = (d: Detail) => {
      if (d.events.length) after.current = d.events[d.events.length - 1].id;
      handler.current(d);
    };

    const poll = async () => {
      if (stopped) return;
      try {
        const d = await call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId }, query: { after: after.current } } }));
        if (stopped) return;
        take(d);
        if (FINAL.has(d.status)) return;
      } catch {
        // A failed look is tried again on the next tick, as polling always did.
      }
      timer = setTimeout(poll, POLL_MS);
    };

    if (typeof EventSource === "undefined") {
      poll();
      return () => {
        stopped = true;
        clearTimeout(timer);
      };
    }

    const source = new EventSource(`${BASE}/api/runs/${runId}/live?after=${after.current}`);
    source.onmessage = (message) => {
      const d = JSON.parse(message.data) as Detail;
      take(d);
      // The stream ends with the Run; without this the browser would reconnect to ask again.
      if (FINAL.has(d.status)) source.close();
    };
    source.onerror = () => {
      // A dropped connection is retried by the browser (carrying on from Last-Event-ID). One that was
      // refused outright is closed: poll instead.
      if (source.readyState === EventSource.CLOSED && !stopped) poll();
    };
    return () => {
      stopped = true;
      source.close();
      clearTimeout(timer);
    };
  }, [runId, live]);
}

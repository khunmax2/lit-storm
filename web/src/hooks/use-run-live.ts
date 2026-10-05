// A Run's progress as it happens: the API pushes each change (GET /api/runs/{id}/live, server-sent
// events, woken by Postgres) and this hands every message to `onDetail`. Where the stream cannot be had —
// no EventSource, or a proxy that refuses it — it asks every 2.5 s instead, as the pages used to.
//
// Everything on a page watching one Run shares one stream (a browser allows only a few connections to a
// site at once). A watcher that joins late hears messages from then on; what came before, it reads itself.
import { useEffect, useRef } from "react";

import { api, BASE, call, type Schemas } from "@/api/client";

type Detail = Schemas["RunDetail"];
type Listener = (d: Detail) => void;

const POLL_MS = 2500;
const FINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

const watching = new Map<string, { listeners: Set<Listener>; stop: () => void }>();

/** Start watching a Run; `emit` is called with each message. Returns the way to stop. */
function watch(runId: string, emit: Listener): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let after = 0; // the last event id seen: a fallback poll starts there

  const take = (d: Detail) => {
    if (d.events.length) after = d.events[d.events.length - 1].id;
    emit(d);
  };

  const poll = async () => {
    if (stopped) return;
    try {
      const d = await call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId }, query: { after } } }));
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

  const source = new EventSource(`${BASE}/api/runs/${runId}/live?after=0`);
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
}

export function useRunLive(runId: string, live: boolean, onDetail: Listener) {
  // The newest callback, so a message is read against the page as it is now.
  const handler = useRef(onDetail);
  handler.current = onDetail;

  useEffect(() => {
    if (!live) return;
    const listener: Listener = (d) => handler.current(d);
    let entry = watching.get(runId);
    if (!entry) {
      const listeners = new Set<Listener>();
      entry = { listeners, stop: watch(runId, (d) => listeners.forEach((l) => l(d))) };
      watching.set(runId, entry);
    }
    entry.listeners.add(listener);
    const joined = entry;
    return () => {
      joined.listeners.delete(listener);
      if (!joined.listeners.size) {
        joined.stop();
        watching.delete(runId);
      }
    };
  }, [runId, live]);
}

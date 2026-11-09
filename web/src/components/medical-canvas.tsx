// Medical Review's run, as MedicalReviewerAgent works through it (docs/adr/0013): the question framed as
// PICO, the searches, the screening funnel, then one card per paper as it is read, coloured by what the
// numbers said and marked when two models disagreed, and the synthesis. Built from the Run's "medical"
// notes, each one of MRA's own events (server: engines/medical/engine.py).
import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, CheckCircle2, Filter, Loader2, Search, Sparkles, TriangleAlert, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api, call, type Schemas } from "@/api/client";
import { useRunLive } from "@/hooks/use-run-live";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

type Note = { event: string; seq?: number } & Record<string, unknown>;
type Paper = { ref: string; title: string; done: boolean; ok?: boolean; verified?: number; uncertain?: boolean; direction?: string | null; design?: string | null };
type Model = {
  question?: string;
  assumptions: string[];
  queries: string[];
  found?: number;
  candidates?: number;
  screened?: { kept: number; total: number };
  batches: number;
  papers: Paper[];
  pools?: number;
  ended?: string;
  cost?: number;
  step: number; // 0 refine, 1 search, 2 screen, 3 read, 4 synthesize, 5 done
};

const STEP_OF: Record<string, number> = {
  checking_topic: 0, refining: 0, question_refined: 0, planning: 1, searching: 1, enriching: 1,
  screening: 2, screened: 2, external_lookup: 3, citations_fetched: 3, reading: 3, extracted: 3,
  synthesizing: 4, pooled: 4, localizing: 4, finalizing: 4, done: 5, error: 5, rejected: 5, cancelled: 5,
};
const STEPS: { key: string; icon: LucideIcon }[] = [
  { key: "refine", icon: Sparkles },
  { key: "search", icon: Search },
  { key: "screen", icon: Filter },
  { key: "read", icon: BookOpenCheck },
  { key: "synthesize", icon: CheckCircle2 },
];
// Which way a paper's numbers pointed (MRA's `direction`; "null" means no association). A direction, not a
// verdict: fewer events can be the good outcome, so no green for good or red for bad.
const TONE: Record<string, string> = {
  positive: "bg-sky-500", negative: "bg-orange-500", null: "bg-muted-foreground/50", mixed: "bg-violet-500", unclear: "bg-muted-foreground/30",
};

// MRA's design categories, as people write them.
const DESIGN: Record<string, string> = {
  rct: "RCT", sr_ma_rct: "SR/MA of RCTs", sr_ma_observational: "SR/MA of observational studies", sr_ma_mixed: "SR/MA (mixed)",
  non_randomized_trial: "Non-randomised trial", cohort: "Cohort", case_control: "Case-control", cross_sectional: "Cross-sectional",
  qualitative: "Qualitative", mixed_methods: "Mixed methods",
};
const design = (code: string) => DESIGN[code] ?? code.replace(/_/g, " ");

function fold(notes: Note[]): Model {
  const m: Model = { assumptions: [], queries: [], batches: 0, papers: [], step: 0 };
  const paper = (ref: string) => {
    let p = m.papers.find((x) => x.ref === ref);
    if (!p) m.papers.push((p = { ref, title: ref, done: false }));
    return p;
  };
  for (const n of notes) {
    m.step = Math.max(m.step, STEP_OF[n.event] ?? m.step);
    switch (n.event) {
      case "question_refined":
        m.question = (n.refined_question as string) || (n.interpretation as string);
        m.assumptions = (n.assumptions as string[]) ?? [];
        break;
      case "planning":
        m.queries = (n.queries as string[]) ?? [];
        break;
      case "searching":
        m.found = n.found as number;
        break;
      case "enriching":
        m.candidates = n.candidates as number;
        break;
      case "screening":
        m.batches += 1;
        break;
      case "screened":
        m.screened = { kept: n.kept as number, total: n.total as number };
        break;
      case "reading":
        paper(n.ref as string).title = (n.title as string) || (n.ref as string);
        break;
      case "extracted":
        Object.assign(paper(n.ref as string), {
          done: true, ok: n.ok as boolean, verified: n.verified as number, uncertain: n.uncertain as boolean,
          direction: n.direction as string | null, design: n.design as string | null,
        });
        break;
      case "pooled":
        m.pools = n.pools as number;
        break;
      case "done":
      case "error":
      case "rejected":
      case "cancelled":
        m.ended = n.event;
        m.cost = n.cost_usd as number | undefined;
        break;
    }
  }
  return m;
}

export function MedicalCanvas({ runId, live }: { runId: string; live: boolean }) {
  const { t } = useT();
  const [notes, setNotes] = useState(() => new Map<number, Note>());
  const after = useRef(0);
  const take = (events: Schemas["EventOut"][]) => {
    const mine = events.filter((e) => e.type === "note" && e.data.kind === "medical");
    if (!mine.length) return;
    setNotes((prev) => {
      const next = new Map(prev);
      for (const e of mine) next.set(e.id, e.data as unknown as Note);
      return next;
    });
  };
  // Every note so far, page by page; while the Run works, the rest as they come.
  const loaded = useQuery({
    queryKey: ["medical-canvas", runId],
    queryFn: async () => {
      const all: Schemas["EventOut"][] = [];
      for (;;) {
        const r = await call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId }, query: { after: after.current } } }));
        if (!r.events.length) break;
        after.current = r.events[r.events.length - 1].id;
        all.push(...r.events);
        if (r.events.length < 500) break;
      }
      return all;
    },
  });
  useEffect(() => take(loaded.data ?? []), [loaded.data]); // eslint-disable-line react-hooks/exhaustive-deps
  useRunLive(runId, live, (d) => take(d.events));
  const m = useMemo(() => fold([...notes.entries()].sort((a, b) => a[0] - b[0]).map(([, n]) => n)), [notes]);

  if (!notes.size) return <p className="text-xs text-muted-foreground">{live ? t("flow.waiting") : t("flow.none")}</p>;
  const working = (i: number) => live && !m.ended && m.step === i;
  const done = (i: number) => m.step > i || m.ended === "done";
  return (
    <div className="grid gap-4 rounded-xl border bg-muted/30 p-4 text-sm">
      {/* The review's steps, the one at work turning. */}
      <ol className="flex flex-wrap items-center gap-1.5">
        {STEPS.map((s, i) => {
          const Icon = working(i) ? Loader2 : s.icon;
          return (
            <li key={s.key} className="flex items-center gap-1.5">
              {i > 0 && <span className={cn("h-px w-4 transition-colors", done(i - 1) ? "bg-brand" : "bg-border")} />}
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                  working(i) && "border-brand bg-brand-soft text-brand",
                  done(i) && !working(i) && "border-brand/40 text-foreground",
                  !done(i) && !working(i) && "text-muted-foreground",
                )}
              >
                <Icon className={cn("size-3.5", working(i) && "animate-spin motion-reduce:animate-none")} />
                {t(`medicalCanvas.step.${s.key}` as Key)}
              </span>
            </li>
          );
        })}
      </ol>

      {m.question && (
        <div className="grid gap-1 rounded-lg border bg-card p-3 animate-in fade-in-0 duration-300">
          <span className="text-xs font-medium text-brand">{t("medicalCanvas.question")}</span>
          <span>{m.question}</span>
          {m.assumptions.length > 0 && (
            <span className="text-xs text-muted-foreground">{t("medicalCanvas.assumptions")}: {m.assumptions.join("; ")}</span>
          )}
        </div>
      )}

      {(m.queries.length > 0 || m.found != null) && (
        <div className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            {t("medicalCanvas.searched", { n: m.queries.length })}
            {m.found != null && ` · ${t("medicalCanvas.found", { n: m.found })}`}
            {m.candidates != null && ` · ${t("medicalCanvas.withAbstracts", { n: m.candidates })}`}
          </span>
          <div className="flex flex-wrap gap-1.5">
            {m.queries.map((q) => (
              <span key={q} className="max-w-full truncate rounded-md bg-card px-2 py-0.5 font-mono text-[11px] text-muted-foreground ring-1 ring-border">
                {q}
              </span>
            ))}
          </div>
        </div>
      )}

      {(m.screened || m.batches > 0) && (
        <div className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            {m.screened
              ? t("medicalCanvas.screened", { kept: m.screened.kept, total: m.screened.total })
              : t("medicalCanvas.screening", { n: m.batches * 10 })}
          </span>
          {m.screened && m.screened.total > 0 && (
            <div className="h-2 overflow-hidden rounded-full bg-border">
              <div
                className="h-full rounded-full bg-brand transition-[width] duration-700 ease-out"
                style={{ width: `${Math.max(4, (100 * m.screened.kept) / m.screened.total)}%` }}
              />
            </div>
          )}
        </div>
      )}

      {m.papers.length > 0 && (
        <div className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            {t("medicalCanvas.reading", { done: m.papers.filter((p) => p.done).length, n: m.papers.length })}
          </span>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {m.papers.map((p) => (
              <li
                key={p.ref}
                className={cn(
                  "flex items-start gap-2 rounded-lg border bg-card px-2.5 py-2 animate-in fade-in-0 zoom-in-95 duration-300 motion-reduce:animate-none",
                  !p.done && live && "border-brand/40",
                )}
              >
                <span
                  className={cn(
                    "mt-1.5 size-2 shrink-0 rounded-full",
                    p.done ? (TONE[p.direction ?? "unclear"] ?? TONE.unclear) : "animate-pulse bg-brand",
                  )}
                  title={p.direction ? t(`medicalCanvas.direction.${p.direction}` as Key) : undefined}
                />
                <span className="grid min-w-0 gap-0.5">
                  <span className="truncate text-xs font-medium">{p.title}</span>
                  <span className="flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
                    <span>{p.ref}</span>
                    {p.design && <span>{design(p.design)}</span>}
                    {p.done && p.ok && (p.verified ?? 0) > 0 && (
                      <span className="text-success">✓ {t("medicalCanvas.verified", { n: p.verified ?? 0 })}</span>
                    )}
                    {p.done && p.ok && !p.verified && <span>{t("medicalCanvas.noNumbers")}</span>}
                    {p.done && p.ok === false && <span>{t("medicalCanvas.notRead")}</span>}
                    {p.uncertain && (
                      <span className="inline-flex items-center gap-0.5 text-warning">
                        <TriangleAlert className="size-3" />
                        {t("medicalCanvas.uncertain")}
                      </span>
                    )}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(m.step >= 4 || m.ended) && (
        <span className="text-xs text-muted-foreground">
          {m.pools != null && `${t("medicalCanvas.pools", { n: m.pools })} · `}
          {m.ended === "done"
            ? t("medicalCanvas.done") + (m.cost != null ? ` · $${m.cost.toFixed(3)}` : "")
            : m.ended
              ? t(`medicalCanvas.ended.${m.ended}` as Key)
              : t("medicalCanvas.synthesizing")}
        </span>
      )}
    </div>
  );
}

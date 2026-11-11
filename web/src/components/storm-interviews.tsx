// A STORM Run's interviews (GET /api/runs/{id}/interviews): each perspective
// asked a topic expert, who searched the web and answered. What the report was
// written from, shown under the Run on its Session page, a tab per perspective.
// Answers are model output: rendered by markdown-it with raw HTML left as text,
// and each [n] links to the nth page found for that question.
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Globe, MessageSquareText, Search } from "lucide-react";
import MarkdownIt from "markdown-it";
import { useState } from "react";

import { api, call } from "@/api/client";
import { domainOf } from "@/components/common";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

type Source = { title: string; url: string };
type Turn = { question: string; queries: string[]; answer: string; sources: Source[] };
type Perspective = { name: string; description: string; turns: Turn[] };

const md = new MarkdownIt({ html: false, linkify: false });

const escape = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** The answer as HTML, its [n] markers links to the pages the expert found. */
function answerHtml(text: string, sources: Source[]) {
  return md.render(text).replace(/\[(\d+)\]/g, (whole, n) => {
    const s = sources[Number(n) - 1];
    if (!s || !/^https?:\/\//.test(s.url)) return whole;
    return `<a class="iv-cite" href="${escape(s.url)}" target="_blank" rel="noreferrer" title="${escape(s.title || s.url)}">${n}</a>`;
  });
}

const TONES = [
  "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-200",
  "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-200",
  "bg-teal-100 text-teal-800 dark:bg-teal-500/15 dark:text-teal-200",
  "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-200",
  "bg-pink-100 text-pink-800 dark:bg-pink-500/15 dark:text-pink-200",
];
const tint = (i: number) => TONES[i % TONES.length];
/** Thai roles carry their English name in brackets; the tab has room for one. */
const short = (name: string) => name.split(" (")[0];

function Answer({ turn, n, tone, asker }: { turn: Turn; n: number; tone: string; asker: string }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const shown = turn.sources.slice(0, 3);
  return (
    <article className="space-y-3 rounded-2xl border bg-card p-3 sm:p-4">
      <div className="flex gap-3 rounded-xl bg-muted/50 p-3">
        <span aria-hidden className={cn("flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold", tone)}>
          {n}
        </span>
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            {t("iv.q", { n })} · {asker}
          </p>
          <p className="font-medium leading-relaxed whitespace-pre-line">{turn.question}</p>
          {turn.queries.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Search className="size-3" />
                {t("iv.searched")}
              </span>
              {turn.queries.map((q, i) => (
                <span key={i} className="max-w-full truncate rounded-full border bg-card px-2 py-px text-xs text-foreground/80" title={q}>
                  {q}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex gap-3 px-1 sm:px-3">
        <span
          aria-hidden
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
        >
          <Globe className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="mb-1 text-xs font-medium text-muted-foreground">{t("iv.answer", { n: turn.sources.length })}</p>
          <div
            className={cn("iv-answer text-sm leading-relaxed text-foreground/90", !open && "line-clamp-6")}
            dangerouslySetInnerHTML={{ __html: answerHtml(turn.answer, turn.sources) }}
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t pt-2 sm:pl-14">
        {shown.map((s, i) => (
          <a
            key={i}
            href={s.url}
            target="_blank"
            rel="noreferrer"
            title={s.title}
            className="flex max-w-72 items-center gap-1.5 rounded-lg bg-muted/60 px-2.5 py-1 text-xs hover:bg-muted"
          >
            <b className="shrink-0 font-semibold text-brand">{domainOf(s.url)}</b>
            <span className="truncate text-foreground/80">{s.title}</span>
          </a>
        ))}
        {turn.sources.length > shown.length && (
          <span className="text-xs text-muted-foreground">{t("iv.moreSources", { n: turn.sources.length - shown.length })}</span>
        )}
        <Button variant="outline" size="sm" className="ml-auto" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {t(open ? "iv.less" : "iv.more")}
          <ChevronDown className={cn("transition-transform", open && "rotate-180")} />
        </Button>
      </div>
    </article>
  );
}

function Interviews({ runId }: { runId: string }) {
  const { t } = useT();
  const [tab, setTab] = useState(0);
  const query = useQuery({
    queryKey: ["interviews", runId],
    queryFn: () =>
      call(api.GET("/api/runs/{run_id}/interviews", { params: { path: { run_id: runId } } })) as Promise<{ perspectives: Perspective[] }>,
    staleTime: Infinity,
    retry: false,
  });
  if (query.isLoading) return <p className="text-sm text-muted-foreground">{t("iv.loading")}</p>;
  const all = query.data?.perspectives.filter((p) => p.turns.length) ?? [];
  if (!all.length) return <p className="text-sm text-muted-foreground">{t("iv.none")}</p>;
  const current = all[Math.min(tab, all.length - 1)];
  const at = all.indexOf(current);
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {t("iv.count", { p: all.length, q: all.reduce((a, p) => a + p.turns.length, 0) })} · {t("iv.lead")}
      </p>
      <div role="tablist" aria-label={t("iv.title")} className="flex gap-1.5 overflow-x-auto rounded-xl bg-muted/60 p-1">
        {all.map((p, i) => (
          <button
            key={i}
            type="button"
            role="tab"
            aria-selected={i === at}
            onClick={() => setTab(i)}
            className={cn(
              "flex min-h-11 shrink-0 items-center gap-2 rounded-lg border px-2 py-1.5 pr-3.5 text-left transition-colors",
              i === at ? "border-brand/40 bg-card shadow-xs" : "border-transparent hover:bg-card/60",
            )}
          >
            <span aria-hidden className={cn("flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold", tint(i))}>
              {i + 1}
            </span>
            <span className="flex flex-col">
              <span className="text-[13px] font-medium whitespace-nowrap">{short(p.name)}</span>
              <span className="text-[11px] text-muted-foreground">{t("iv.questions", { n: p.turns.length })}</span>
            </span>
          </button>
        ))}
      </div>
      <div role="tabpanel" className="space-y-3">
        <div className={cn("rounded-xl px-3.5 py-2.5", tint(at))}>
          <p className="text-sm font-semibold">{current.name}</p>
          {current.description && <p className="text-sm">{current.description}</p>}
        </div>
        {current.turns.map((turn, i) => (
          <Answer key={`${at}-${i}`} turn={turn} n={i + 1} tone={tint(at)} asker={short(current.name)} />
        ))}
      </div>
    </div>
  );
}

/** Folded under the Run until opened: the interviews load only then. */
export function StormInterviews({ runId }: { runId: string }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-xl border bg-card/60">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm font-medium"
      >
        <span className="flex size-7 items-center justify-center rounded-lg bg-brand-soft text-brand">
          <MessageSquareText className="size-4" />
        </span>
        <span className="flex-1">{t("iv.title")}</span>
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", !open && "-rotate-90")} />
      </button>
      {open && (
        <div className="border-t p-3">
          <Interviews runId={runId} />
        </div>
      )}
    </section>
  );
}

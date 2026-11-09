"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { Lang } from "@mra/lib/i18n";
import { flowRows, prismaFlow, UNKNOWN_COUNT, type FlowBox, type FlowCount } from "@mra/lib/prisma-flow";
import type { ReviewTypeOrLegacy } from "@mra/lib/review-type";
import type { ReviewMethods, Stats } from "@mra/lib/types";
import { RC } from "@mra/lib/i18n-report";
import { Term } from "../ui/term";
import { ThaiNodes, ThaiText } from "../ui/thai-text";
import { usePrinting } from "./print-mode";
import { L } from "./text";

const F = RC.prisma;

const COUNT = new Intl.NumberFormat("en-US");

/** A system count (display face, tabular figures), or "unknown" when the result does not record it. */
function Count({ value, lang, n = false }: { value: FlowCount; lang: Lang; n?: boolean }) {
  if (value == null) return <span className="font-display whitespace-nowrap text-muted" data-unknown>{UNKNOWN_COUNT[lang]}</span>;
  return <span className="font-display whitespace-nowrap tabular-nums">{n && "n = "}{COUNT.format(value)}</span>;
}

/** Plan 21: a note whose figures are counts (requested N, a shortfall's E of N): each figure in the display face. */
function CountNote({ text }: { text: string }) {
  return (
    <p className="text-[12px] leading-[1.6] text-muted" data-count-note>
      <ThaiNodes>{text.split(/(\d+)/).map((part, i) => (i % 2
        ? <span key={i} className="font-display whitespace-nowrap tabular-nums">{part}</span> : part))}</ThaiNodes>
    </p>
  );
}

/** Records per source, with a bar against the largest source: a count is printed on every row. */
function SourceBars({ box }: { box: FlowBox }) {
  const max = Math.max(1, ...box.lines.map((l) => l.value ?? 0));
  return (
    <ul className="grid">
      {box.lines.map((l) => (
        <li key={l.key} data-flow-line={l.key} className="grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_24px] items-center gap-2 text-[12px] leading-[1.9]">
          <span className="truncate" title={l.label}>{l.label}</span>
          <span aria-hidden="true" className="block h-1.5 overflow-hidden rounded-[3px] bg-rail">
            <span className="block h-full bg-sup" style={{ width: `${((l.value ?? 0) / max) * 100}%` }} />
          </span>
          <b className="text-right font-semibold tabular-nums">{l.value ?? "–"}</b>
        </li>
      ))}
    </ul>
  );
}

function Box({ box, lang, side, big = false, final = false }: { box: FlowBox; lang: Lang; side: boolean; big?: boolean; final?: boolean }) {
  const sources = big && box.lines.length > 0 && box.lines.every((l) => l.key.startsWith("source:"));
  return (
    <div data-flow-box={box.key}
      className={`grid min-w-0 content-start gap-1.5 rounded-[10px] p-3.5 ${final ? "mra-flow-final" : side ? "bg-rail" : "border border-rule bg-surface"}`}>
      <p className={`leading-snug font-semibold break-words ${side ? "text-[13px]" : "text-[15px]"}`}><ThaiText>{box.title}</ThaiText></p>
      {box.value !== undefined && <p className={`leading-tight font-bold ${big ? "text-[28px]" : "text-[1.15rem]"}`}><Count value={box.value} lang={lang} n /></p>}
      {sources ? <SourceBars box={box} /> : box.lines.length > 0 && (
        <ul className="grid">
          {box.lines.map((l) => (
            <li key={l.key} data-flow-line={l.key}
              className="flex items-baseline justify-between gap-3 border-t border-rule py-1 text-[13px] leading-[1.5] first:border-t-0">
              <span className="min-w-0 break-words">
                <ThaiText>{l.label}</ThaiText>
                {l.note && <span className="block text-[0.76rem] text-muted"><ThaiText>{l.note}</ThaiText></span>}
              </span>
              <Count value={l.value} lang={lang} />
            </li>
          ))}
        </ul>
      )}
      {box.notes.map((n) => <p key={n} className="text-[12px] leading-[1.6] text-muted"><ThaiText>{n}</ThaiText></p>)}
      {box.countNote && <CountNote text={box.countNote} />}
    </div>
  );
}

function ArrowDown() {
  return (
    <svg aria-hidden="true" viewBox="0 0 12 28" className="mx-auto h-7 w-3 text-muted">
      <path d="M6 0V25" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M1.5 20.5L6 26.5L10.5 20.5" stroke="currentColor" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

/** Narrow layout: the exclusion box hangs off its stage (down, then right). */
function ArrowCorner({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 24" className={`h-6 w-5 shrink-0 text-muted ${className}`}>
      <path d="M3 0V18H17" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M12.5 13.5L18.5 18L12.5 22.5" stroke="currentColor" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

/**
 * Study selection (Plan 20 Task 4): a PRISMA 2020 flow (PRISMA-ScR wording for scoping reviews) of ruled boxes built only
 * from result.stats and the per-source counts in result.methods; "unknown" where the result has no count. From a 48rem
 * card it reads left to right, the records leaving under each stage; narrower it runs down the page with each exclusion
 * box indented. The same flow is a table behind the switch by the heading.
 */
export function PrismaFlow({ stats, methods, options, type, lang, heading }: {
  stats: Stats | undefined; methods?: ReviewMethods; options?: Record<string, unknown> | null; type: ReviewTypeOrLegacy; lang: Lang;
  /** the section's heading, on the row of the chart/table switch */
  heading: ReactNode;
}) {
  const view = useMemo(() => prismaFlow({ stats, methods, options, type, lang }), [stats, methods, options, type, lang]);
  const [asTable, setAsTable] = useState(false);
  const printing = usePrinting();
  if (!view) return null;
  const title = L(lang, F.title);
  const rows = flowRows(view);
  const last = view.stages.length - 1;
  // the boxes are the printed flow; the table twin would print it twice (Plan 20 Task 8 fix round 1)
  const table = asTable && !printing;
  return (
    <figure className="@container grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" data-prisma-flow={view.framework}>
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-baseline gap-x-2">
          {heading}
          <span className="text-[14px] font-medium text-muted">{L(lang, F.diagram)} <Term k="prisma" lang={lang}>{view.framework}</Term></span>
        </span>
        <button type="button" onClick={() => setAsTable((t) => !t)} aria-pressed={asTable} className="rbtn print:hidden">
          {L(lang, asTable ? RC.charts.showChart : F.asTableShort)}
        </button>
      </figcaption>
      {table ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[14px]" data-prisma-table>
            <caption className="sr-only">{`${title} (${view.framework})`}</caption>
            <thead>
              <tr className="border-b border-rule">
                <th scope="col" className="py-1.5 pr-3 text-left label">{L(lang, F.stage)}</th>
                <th scope="col" className="py-1.5 pr-3 text-left label">{L(lang, F.item)}</th>
                <th scope="col" className="py-1.5 text-right label">{L(lang, F.count)}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-rule align-top">
                  <td className="py-1.5 pr-3 text-muted">{r.stage}</td>
                  <th scope="row" className={`py-1.5 pr-3 text-left break-words ${r.note ? "pl-4 text-[0.82rem] font-normal text-muted" : r.depth ? "pl-4 font-normal" : "font-semibold"}`}>
                    {r.label}
                    {r.detail && <span className="block text-[0.78rem] font-normal text-muted">{r.detail}</span>}
                  </th>
                  <td className="py-1.5 text-right">
                    {r.value !== undefined ? <Count value={r.value} lang={lang} />
                      : <span className="sr-only">{L(lang, r.note ? F.noteNoCount : F.noTotal)}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          {/* wide: one column per stage, the stage's name, its box, then the records leaving there */}
          <ol className="hidden min-w-0 gap-3.5 @[48rem]:grid print:hidden" aria-label={`${title} ${view.framework}`}
            style={{ gridTemplateColumns: `repeat(${view.stages.length}, minmax(0, 1fr))`, gridTemplateRows: "auto auto auto" }}>
            {view.stages.map((st, i) => (
              <li key={st.key} data-flow-stage={st.key} className="row-span-3 grid min-w-0 grid-rows-subgrid gap-3.5">
                <p className="text-[13px] font-semibold"><span className="tabular-nums">{i + 1}</span> · <ThaiText>{st.label}</ThaiText></p>
                <Box box={st.main} lang={lang} side={false} big final={i === last} />
                {st.side ? <Box box={st.side} lang={lang} side /> : <span />}
              </li>
            ))}
          </ol>
          <ol className="grid min-w-0 grid-cols-[minmax(0,1fr)] @[48rem]:hidden print:grid" aria-label={`${title} ${view.framework}`}>
            {view.stages.map((st, i) => (
              <li key={st.key} data-flow-stage={st.key} className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2">
                <p className="text-[13px] font-semibold"><span className="tabular-nums">{i + 1}</span> · <ThaiText>{st.label}</ThaiText></p>
                <Box box={st.main} lang={lang} side={false} final={i === last} />
                {st.side && (
                  <div className="flex min-w-0 items-start gap-1.5 pl-2">
                    <ArrowCorner />
                    <div className="grid min-w-0 flex-1"><Box box={st.side} lang={lang} side /></div>
                  </div>
                )}
                {i < last && <span data-flow-arrow><ArrowDown /></span>}
              </li>
            ))}
          </ol>
        </>
      )}
    </figure>
  );
}

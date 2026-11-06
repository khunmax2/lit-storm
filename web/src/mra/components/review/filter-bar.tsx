"use client";

import { useId, type ReactNode } from "react";
import { designKey, designLabel, emptyFilters, isFiltered, isNonQuantitative, questionDirection, type Filters } from "@mra/lib/charts-data";
import { DIRECTION_LABEL, DIRECTION_ORDER, ROB_LABEL, type Lang } from "@mra/lib/i18n";
import { RC } from "@mra/lib/i18n-report";
import type { Paper, RiskOfBias } from "@mra/lib/types";
import { Term } from "../ui/term";
import { L } from "./text";

const F = RC.filter;

const RISKS: RiskOfBias[] = ["low", "moderate", "high", "unclear"];

/** One-line reminder above the charts and the paper list when filters hide some papers. */
export function FilterStatus({ filters, onChange, shown, total, lang }: {
  filters: Filters; onChange: (f: Filters) => void; shown: number; total: number; lang: Lang;
}) {
  if (!isFiltered(filters)) return null;
  return (
    <p role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-sm bg-info-bg px-3 py-2 text-[0.88rem]">
      <span>{L(lang, F.status(shown, total))}</span>
      <button type="button" onClick={() => onChange(emptyFilters())} className="min-h-11 font-display font-semibold text-primary underline underline-offset-2 md:min-h-0 print:hidden">
        {L(lang, F.clear)}
      </button>
    </p>
  );
}

/** A row of chips: "all" clears the row, each other chip toggles its value. */
function ChipRow<T extends string>({ label, values, chosen, nameOf, onChange, allLabel }: {
  label: ReactNode; values: T[]; chosen: T[]; nameOf: (v: T) => string; onChange: (next: T[]) => void; allLabel: string;
}) {
  return (
    <div role="group" className="flex flex-wrap items-center gap-1.5">
      <span className="w-[108px] flex-none text-[13px] text-muted">{label}</span>
      <button type="button" className="rchip" aria-pressed={chosen.length === 0} onClick={() => onChange([])}>{allLabel}</button>
      {values.map((v) => (
        <button key={v} type="button" className="rchip" aria-pressed={chosen.includes(v)}
          onClick={() => onChange(chosen.includes(v) ? chosen.filter((x) => x !== v) : [...chosen, v])}>{nameOf(v)}</button>
      ))}
    </div>
  );
}

/** The filters as rows of chips above the studies; relevance and years behind a disclosure. They scope every table and chart. */
export function FilterBar({ papers, filters, onChange, lang, showRisk = true, showDirection = true }: {
  papers: Paper[]; filters: Filters; onChange: (f: Filters) => void; lang: Lang; showRisk?: boolean; showDirection?: boolean;
}) {
  const id = useId();
  const years = papers.map((p) => p.year).filter((y): y is number => typeof y === "number");
  const minYear = years.length ? Math.min(...years) : null;
  const maxYear = years.length ? Math.max(...years) : null;
  const cards = papers.map((p) => p.card_en ?? p.card);
  const designs = [...new Set(cards.flatMap((c) => (c ? [designKey(c)] : [])))].sort();
  const directions = DIRECTION_ORDER.filter((d) => cards.some((c) => c && !isNonQuantitative(c) && questionDirection(c) === d));
  const risks = RISKS.filter((r) => cards.some((c) => c?.risk_of_bias === r));
  const yearOptions = minYear != null && maxYear != null ? Array.from({ length: maxYear - minYear + 1 }, (_, i) => minYear + i) : [];
  const all = L(lang, F.all);

  return (
    <div role="group" aria-label={L(lang, F.group)} className="grid gap-2 print:hidden">
      {designs.length > 1 && (
        <ChipRow label={<Term k="studyDesign" lang={lang}>{L(lang, F.design)}</Term>} values={designs} chosen={filters.designs} allLabel={all}
          nameOf={(d) => designLabel(d, lang)} onChange={(next) => onChange({ ...filters, designs: next })} />
      )}
      {showDirection && directions.length > 1 && (
        <ChipRow label={L(lang, F.direction)} values={directions} chosen={filters.directions} allLabel={all}
          nameOf={(d) => DIRECTION_LABEL[lang][d]} onChange={(next) => onChange({ ...filters, directions: next })} />
      )}
      {showRisk && risks.length > 1 && (
        <ChipRow label={<Term k="riskOfBias" lang={lang}>{L(lang, F.rob)}</Term>} values={risks} chosen={filters.risk} allLabel={all}
          nameOf={(r) => ROB_LABEL[lang][r]} onChange={(next) => onChange({ ...filters, risk: next })} />
      )}
      <details className="text-[13px]">
        <summary className="cursor-pointer py-1 font-medium text-muted">{L(lang, F.more)}</summary>
        <div className="mt-2 flex flex-wrap items-end gap-x-6 gap-y-3">
          <div className="grid gap-1">
            <label htmlFor={`${id}-rel`} className="label">{L(lang, F.relevance)}: <span className="text-ink">{filters.minRelevance}</span></label>
            <input id={`${id}-rel`} type="range" min={0} max={100} step={5} value={filters.minRelevance}
              onChange={(e) => onChange({ ...filters, minRelevance: Number(e.target.value) })} className="w-36 accent-primary" />
            <p className="max-w-[16rem] text-[12px] text-muted">
              {L(lang, F.relevanceHint)}
              <Term k="relevance" lang={lang} />
            </p>
          </div>
          {yearOptions.length > 1 && (
            <div className="flex items-end gap-2">
              <div className="grid gap-1">
                <label htmlFor={`${id}-from`} className="label">{L(lang, F.from)}</label>
                <select id={`${id}-from`} value={filters.yearFrom ?? ""} onChange={(e) => onChange({ ...filters, yearFrom: e.target.value ? Number(e.target.value) : null })}
                  className="rounded-sm border border-rule bg-surface px-2 py-1 text-ink">
                  <option value="">{L(lang, F.any)}</option>
                  {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
              <div className="grid gap-1">
                <label htmlFor={`${id}-to`} className="label">{L(lang, F.to)}</label>
                <select id={`${id}-to`} value={filters.yearTo ?? ""} onChange={(e) => onChange({ ...filters, yearTo: e.target.value ? Number(e.target.value) : null })}
                  className="rounded-sm border border-rule bg-surface px-2 py-1 text-ink">
                  <option value="">{L(lang, F.any)}</option>
                  {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>
          )}
        </div>
      </details>
      {isFiltered(filters) && (
        <button type="button" onClick={() => onChange(emptyFilters())} className="rbtn w-fit">{L(lang, F.clear)}</button>
      )}
    </div>
  );
}

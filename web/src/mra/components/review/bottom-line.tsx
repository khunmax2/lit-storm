"use client";

import type { ReactNode } from "react";
import { directionTally, hasPooledPapers, themePapers } from "@mra/lib/charts-data";
import { META_POOL_COPY } from "@mra/lib/copy";
import { DIRECTION_LABEL, DIRECTION_ORDER, type Lang } from "@mra/lib/i18n";
import { fieldLang, RC } from "@mra/lib/i18n-report";
import { DESIGN_GROUP_LABEL, fixed } from "@mra/lib/meta-view";
import { metaPoolGap, reviewTypeOf, showsDirection } from "@mra/lib/review-type";
import type { Direction, Paper, Pool, ReviewResult, Synthesis } from "@mra/lib/types";
import { ComputedNumber, Glyph } from "../ui/evidence";
import { Term } from "../ui/term";
import { StrengthRationale } from "./report-parts";
import { L } from "./text";

const B = RC.bottom;

const DIRECTION_TOKEN: Record<Direction, string> = { positive: "sup", negative: "harm", null: "none", mixed: "mixed", unclear: "unclear" };

/** The pools in reading order: the graded (primary) outcome first, as the backend computed them. */
function orderedPools(result: ReviewResult): Pool[] {
  const pools = result.meta_analysis?.pools ?? [];
  const primary = result.meta_analysis?.grade?.primary_outcome;
  return [...pools].sort((a, b) => Number(b.outcome === primary) - Number(a.outcome === primary));
}

/** One pooled estimate in a sentence: outcome, group, k, then the computed value and interval (ComputedNumber only). */
export function PooledLine({ pool, lang, english }: { pool: Pool; lang: Lang; english: boolean }) {
  const outcome = english ? pool.outcome : pool.outcome_display || pool.outcome;
  const group = DESIGN_GROUP_LABEL[pool.design_group]?.[lang] ?? pool.design_group;
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-1" data-pooled-line>
      <span className="font-display font-semibold break-words" lang={fieldLang(outcome, lang)}>{outcome}</span>
      <span className="text-[0.88rem] text-muted">{group} · k = <span className="tabular-nums">{pool.k}</span></span>
      <span className="inline-flex flex-wrap items-baseline gap-x-1.5">
        <span className="font-display">{pool.measure}</span>
        <ComputedNumber value={fixed(pool.pooled.est, 2)} lang={lang} />
        <span className="whitespace-nowrap">
          <span className="font-display text-muted">(95% CI </span>
          <ComputedNumber value={`${fixed(pool.pooled.ci_lower, 2)}–${fixed(pool.pooled.ci_upper, 2)}`} lang={lang} tag={false} />
          <span className="font-display text-muted">)</span>
        </span>
      </span>
    </li>
  );
}

/**
 * How to read the answer the band gives (Plan 20's bottom line, its answer now in the band): the pooled value(s) of a
 * meta-analysis (computed) or "could not pool", how the papers split, who wrote what, the notices for this audience, and
 * behind disclosures the grading rationale and how the agent read the question.
 */
export function ReadingCard({ synthesis, result, papers, lang, english, openRationale, notices, question }: {
  synthesis: Synthesis; result: ReviewResult; papers: Paper[]; lang: Lang;
  /** the reader switched a Thai review to English: English pool names */
  english: boolean;
  /** Plan 26: the certainty rationale starts open (learner and committee views) */
  openRationale?: boolean;
  notices: ReactNode;
  question: ReactNode;
}) {
  const hasPapers = papers.length > 0;
  const type = reviewTypeOf(result);
  const tally = directionTally(papers, type === "narrative");
  // Scoping maps what exists; it never tallies a direction of effect.
  const shown = showsDirection(type) ? DIRECTION_ORDER.filter((d) => tally[d] > 0) : [];
  const counted = shown.reduce((sum, d) => sum + tally[d], 0);
  // Qualitative / mixed-methods studies are never tallied by direction; they are counted as themes instead.
  const themes = type === "scoping" ? 0 : themePapers(papers).length;
  const poolGap = metaPoolGap(result);
  const pools = type === "meta_analysis" ? orderedPools(result) : [];
  const hasAnswer = !!(synthesis.answer?.trim() || synthesis.executive_summary || result.summary);
  return (
    <section aria-label={L(lang, B.reading)} className="rc gap-4">
      {poolGap && (
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5 text-[13px]" data-not-pooled={poolGap}>
          {/* a short chip: never wraps (Plan 20 Task 7) */}
          <span className="label nw rounded-sm bg-warn-bg px-2 py-1">{META_POOL_COPY[poolGap].label[lang]}</span>
          <span className="text-muted">{META_POOL_COPY[poolGap].reason[lang]}</span>
        </p>
      )}
      {!hasAnswer && hasPapers && (
        // "" also when the model wrote none or the narrative step failed (api.md): never blamed on the checks
        <p className="text-[13px] text-muted" data-no-answer>{L(lang, B.noAnswer)}</p>
      )}
      {pools.length > 0 && (
        <div className="grid gap-1.5" data-bottom-pools>
          <p className="label">{L(lang, B.pooledLabel)}</p>
          <ul className="grid gap-1.5">
            {pools.map((p, i) => <PooledLine key={`${p.outcome}|${p.design_group}|${p.measure}|${i}`} pool={p} lang={lang} english={english} />)}
          </ul>
        </div>
      )}
      {hasPapers && (
        <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
          {shown.length > 0 && (
            <div className="grid min-w-0 flex-[1_1_320px] content-start gap-2">
              <h2 className="text-[15px] leading-[1.45] font-semibold"><Term k="directionTally" lang={lang}>{L(lang, B.tally)}</Term></h2>
              <div aria-hidden="true" className="flex h-3 overflow-hidden rounded-md bg-rule">
                {shown.filter((d) => d !== "unclear").map((d) => (
                  <span key={d} style={{ width: `${(tally[d] / counted) * 100}%`, background: `var(--${DIRECTION_TOKEN[d]})` }} />
                ))}
              </div>
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted" data-direction-tally>
                {shown.map((d) => (
                  <li key={d} data-direction={d} className="inline-flex items-center gap-1.5">
                    <Glyph direction={d} lang={lang} />
                    {DIRECTION_LABEL[lang][d]} <b className="font-semibold text-ink tabular-nums">{tally[d]}</b>
                  </li>
                ))}
              </ul>
              {hasPooledPapers(papers) && <p className="text-[12px] text-muted">{L(lang, B.overlap)}</p>}
            </div>
          )}
          <div className="grid min-w-0 flex-[999_1_320px] content-start gap-2">
            <p className="text-[13px] leading-[1.65] text-muted">{L(lang, type === "scoping" ? B.modelNoteScoping : B.modelNote)}</p>
            {themes > 0 && <p className="text-[13px] leading-[1.65] text-muted" data-theme-count>{L(lang, B.themes(themes))}</p>}
          </div>
        </div>
      )}
      {notices}
      <div className="grid gap-1 border-t border-rule pt-3 empty:hidden">
        {hasPapers && <StrengthRationale synthesis={synthesis} lang={lang} quality={result.quality} type={type} openRationale={openRationale} />}
        {question}
      </div>
    </section>
  );
}

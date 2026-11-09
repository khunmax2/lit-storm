"use client";

import { useMemo } from "react";
import type { ChartsContent } from "@mra/lib/charts-content";
import type { Lang } from "@mra/lib/i18n";
import { RC } from "@mra/lib/i18n-report";
import type { ReviewResult } from "@mra/lib/types";
import { StudyMapFigure } from "../charts/figures";
import { DtaFigure, ForestPanel, type Arms } from "../charts/forest-plot";
import { readTokens } from "../charts/tokens";
import { useTheme } from "../theme-toggle";
import { SectionHeading } from "./report-nav";
import { L } from "./text";

const C = RC.charts;

/**
 * Results figures, built only from verified values in the (filtered) papers: a forest panel per outcome and measure and
 * the diagnostic-accuracy family. The study selection flow is PrismaFlow (Plan 20 Task 4); the study map is its own card.
 */
export function Charts({ content, result, lang, onSelect }: {
  content: ChartsContent; result: ReviewResult; lang: Lang; onSelect: (ref: string, outcome?: string) => void;
}) {
  const pico = result.question?.pico;
  const arms: Arms = { intervention: pico?.intervention_or_exposure?.trim() || null };
  const { forest, dta } = content;
  const unverified = forest.unplaced.length ? (
    <p className="text-[0.82rem] text-muted" data-forest-left-out>
      <span className="hole mr-2">{L(lang, C.notVerified)}</span>
      {L(lang, C.leftOut)}{" "}
      {forest.unplaced.map((u) => `${u.ref} (${u.outcome})`).join(", ")}
    </p>
  ) : null;
  return (
    <section aria-labelledby="h-charts" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4">
      <SectionHeading id="h-charts">{L(lang, C.h)}</SectionHeading>
      {forest.panels.length > 0 ? (
        <>
          <p className="text-[13px] leading-[1.65] text-muted">
            {L(lang, C.intro)}
            {content.narrative && <> {L(lang, C.narrative)}</>}
          </p>
          <div className="grid min-w-0 grid-cols-[repeat(auto-fit,minmax(min(420px,100%),1fr))] gap-7" data-forest-panels>
            {forest.panels.map((p) => <ForestPanel key={p.key} panel={p} arms={arms} lang={lang} onSelect={onSelect} />)}
          </div>
          {unverified}
        </>
      ) : !content.narrative && !dta && !content.map && (
        <div className="grid gap-2">
          <p className="text-[0.9rem] text-muted">{L(lang, C.none)}</p>
          {unverified}
        </div>
      )}
      {dta && <DtaFigure data={dta} lang={lang} onSelect={onSelect} />}
    </section>
  );
}

/** Whether Charts has anything to show once the study map has its own card. */
export function hasForestCard(content: ChartsContent): boolean {
  return !content.empty && (content.forest.panels.length > 0 || !!content.dta || (!content.map && !content.narrative));
}

/** The study map (year × sample size × direction), in its own card next to the findings table. */
export function StudyMap({ content, lang, onSelect }: { content: ChartsContent; lang: Lang; onSelect: (ref: string, outcome?: string) => void }) {
  const theme = useTheme();
  const tokens = useMemo(() => (theme ? readTokens() : null), [theme]);
  const { map } = content;
  if (!map || !tokens) return null;
  return <StudyMapFigure points={map.points} missing={map.missing} tokens={tokens} lang={lang} onSelect={onSelect} />;
}

"use client";

import type { ReactNode } from "react";
import { directionTally } from "@mra/lib/charts-data";
import type { Lang } from "@mra/lib/i18n";
import { STRENGTH_LABEL } from "@mra/lib/i18n";
import { fieldLang, LANGUAGE_NAME, RC } from "@mra/lib/i18n-report";
import { reportDate, sourceNames } from "@mra/lib/report-view";
import { isGraded, REVIEW_TYPE_LABEL, showsDirection, type ReviewTypeOrLegacy } from "@mra/lib/review-type";
import { includedCounts } from "@mra/lib/trial-reports";
import type { Audience } from "@mra/lib/audience";
import type { EvidenceStrength, Paper, Review, ReviewResult, Synthesis } from "@mra/lib/types";
import { CopyLinkButton } from "../ui/copy-link";
import { ThaiText } from "../ui/thai-text";
import { AudienceSwitch } from "./audience";
import { CitedText, hasCheckedMark, SupportLegend, type MarkerSupport, type Select } from "./report-parts";
import { L } from "./text";

const T = RC.title;
const P = RC.parts;
const LEVELS: EvidenceStrength[] = ["very_low", "low", "moderate", "high"];

/** The fixed status line in the band: what this report is and is not. */
export function statusText(type: ReviewTypeOrLegacy, lang: Lang): string {
  return L(lang, type === "legacy" ? T.statusLegacy : T.status);
}

function Stat({ label, value, note, accent, children }: { label: string; value: ReactNode; note?: ReactNode; accent?: boolean; children?: ReactNode }) {
  return (
    <div className="mra-stat">
      <p className="text-[13px] leading-normal text-muted">{label}</p>
      <div className="flex flex-none flex-col items-end gap-0.5 text-right">
        <p className={`text-[20px] leading-[1.3] font-semibold ${accent ? "text-[var(--band-accent)]" : ""}`}>{value}</p>
        {children}
        {note && <p className="text-[12px] leading-[1.4] text-muted">{note}</p>}
      </div>
    </div>
  );
}

/** The grade as dots (one to four filled); the level is written beside it, so they are hidden from screen readers. */
function LevelDots({ level }: { level: EvidenceStrength }) {
  const n = LEVELS.indexOf(level) + 1;
  return (
    <span aria-hidden="true" className="flex gap-1">
      {LEVELS.map((l, i) => (
        <span key={l} className="size-2 rounded-full border-[1.5px]"
          style={i < n ? { background: "var(--band-accent)", borderColor: "var(--band-accent)" } : { borderColor: "var(--band-off)" }} />
      ))}
    </span>
  );
}

/**
 * The band that opens the report, across the whole page: what the review asked, the answer and what it is (automated,
 * abstracts only), with the four figures a reader weighs it by beside it. A figure the review has no value for is left
 * out, never filled in: a type that does not grade evidence never reads as "very low".
 */
export function AnswerBand({ review, result, synthesis, type, lang, papers, refs, marks, poolGap, onSelect }: {
  review: Review; result: ReviewResult; synthesis: Synthesis; type: ReviewTypeOrLegacy; lang: Lang; papers: Paper[]; refs: Set<string>;
  /** Plan 25: the badge on the lead's citations when the summary leads (a result without an answer) */
  marks: MarkerSupport | null;
  poolGap: "none" | "failed" | null;
  onSelect: Select;
}) {
  const question = result.question;
  const text = lang === "en" && question?.english ? question.english : question;
  const typed = question?.original_topic || review.topic;
  const refined = text?.refined_question || (lang === "en" ? question?.english_topic : null) || typed;
  const date = reportDate(result.methods?.searched_at ?? review.started_at ?? review.created_at, lang);
  const sources = sourceNames(result.methods?.sources);
  const lead = synthesis.answer?.trim() || synthesis.executive_summary || result.summary || "";
  const line = [
    type === "legacy" ? null : REVIEW_TYPE_LABEL[type][lang],
    date ? L(lang, T.searchedOn(date)) : null,
    sources.length ? L(lang, T.sourcesCount(sources.length)) : null,
    L(lang, T.idLine(review.id.slice(0, 8))),
  ].filter(Boolean).join(" · ");

  const hasPapers = papers.length > 0;
  const { studies, related, unread } = includedCounts(papers);
  const quality = result.quality;
  const grade = hasPapers && isGraded(type) && synthesis.evidence_strength != null ? synthesis.evidence_strength : null;
  const tally = directionTally(papers, type === "narrative");
  const counted = Object.values(tally).reduce((a, b) => a + b, 0);
  const found = result.stats?.found;
  const includedNote = [found != null ? L(lang, T.statFound(found)) : null,
    related > 0 ? L(lang, T.related(related)) : null, unread > 0 ? L(lang, T.unread(unread)) : null].filter(Boolean);

  return (
    <section id="h-answer" aria-labelledby="h-title" className="mra-band scroll-mt-[calc(var(--header-h)+1rem)] lg:col-span-2 print:block">
      <div className="flex min-w-0 flex-[4_1_520px] flex-col gap-2.5">
        <p className="text-[12px] text-muted">{line}</p>
        <h1 id="h-title" lang={fieldLang(refined, lang)} className="text-[28px] leading-[1.4] font-bold break-words">
          <ThaiText>{refined}</ThaiText>
        </h1>
        {refined.trim() !== typed.trim() && (
          <p className="text-[13px] break-words text-muted" data-typed-question>
            {L(lang, T.typed)}: <span lang={fieldLang(typed, lang)}><bdi><ThaiText>{typed}</ThaiText></bdi></span>
          </p>
        )}
        {lead.trim() && (
          <p className="mt-1.5 text-[16px] leading-[1.8] text-[var(--band-text)]" data-prose data-answer={synthesis.answer?.trim() ? "" : undefined} lang={fieldLang(lead, lang)}>
            <CitedText text={lead} onSelect={onSelect} refs={refs} support={marks} />
          </p>
        )}
        {hasCheckedMark(marks) && <SupportLegend lang={lang} />}
        <p className="mt-1.5 text-[12px] leading-[1.65] text-muted" data-status>
          <b className="font-semibold text-ink">{statusText(type, lang)}</b>{" "}
          {L(lang, type === "legacy" ? T.byAgentLegacy : T.byAgent)}
        </p>
        {/* paper has no striped tape or hatch (Plan 20 Task 8): the printout says how its marks read */}
        <p className="hidden text-[0.85rem] print:block" data-print-key>{L(lang, RC.print.key)}</p>
      </div>

      <div className="mra-stats" aria-label={L(lang, T.details)} role="group">
        {grade ? (
          <Stat label={L(lang, T.statCertainty)} value={STRENGTH_LABEL[lang][grade]} accent note={poolGap ? L(lang, P.noBar) : undefined}>
            {!poolGap && <LevelDots level={grade} />}
          </Stat>
        ) : hasPapers && isGraded(type) && type !== "legacy" ? (
          <Stat label={L(lang, T.statCertainty)} value={L(lang, T.statNotAssessed)} />
        ) : null}
        {quality?.numbers_total ? (
          <Stat label={L(lang, T.statVerified)} value={`${Math.round(((quality.numbers_verified ?? 0) / quality.numbers_total) * 100)}%`}
            note={L(lang, T.statVerifiedOf(quality.numbers_verified ?? 0, quality.numbers_total))} />
        ) : null}
        <Stat label={L(lang, T.statIncluded)} value={studies} note={includedNote.length ? includedNote.join(" ") : undefined} />
        {hasPapers && showsDirection(type) && counted > 0 && (
          <Stat label={L(lang, T.statSupport)} value={tally.positive}
            note={L(lang, tally.unclear > 0 ? T.statUnclear(tally.unclear) : T.statOf(counted))} />
        )}
      </div>
    </section>
  );
}

/** PICO (or PCC) as four cards under the band: what the review searched for, in the words the search used. */
export function PicoCards({ question, lang }: { question: ReviewResult["question"]; lang: Lang }) {
  const pico = question?.pico;
  const isPcc = question?.framework === "PCC";
  const rows: [string, string, string | null | undefined][] = isPcc
    ? [["P", L(lang, P.population), pico?.population], ["C", L(lang, P.concept), question?.concept], ["C", L(lang, P.context), question?.context]]
    : pico ? [["P", L(lang, P.population), pico.population], ["I", L(lang, P.intervention), pico.intervention_or_exposure],
      ["C", L(lang, P.comparator), pico.comparator], ["O", L(lang, P.outcomes), pico.outcomes?.join(", ")]] : [];
  const shown = rows.filter(([, , v]) => v?.trim());
  if (!shown.length) return null;
  return (
    <div role="group" aria-label={isPcc ? "PCC" : "PICO"} className="grid grid-cols-[repeat(auto-fit,minmax(230px,1fr))] gap-3">
      {shown.map(([k, label, v]) => (
        <div key={label} className="flex gap-3 rounded-2xl bg-surface px-[18px] py-4">
          <span aria-hidden="true" className="grid size-[34px] flex-none place-items-center rounded-[10px] bg-info-bg font-num font-semibold text-primary">{k}</span>
          <div className="min-w-0">
            <p className="text-[12px] text-muted">{label}</p>
            <p lang={fieldLang(v, lang)} className="mt-0.5 text-[14px] leading-[1.55] font-medium break-words">{v}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Who the report is laid out for, its language, and what can be done with it. */
export function ReportToolbar({ audience, onAudience, lang, original, onLang, hasEnglish, canShare, hasDownloads }: {
  audience: Audience; onAudience: (a: Audience) => void; lang: Lang; original: Lang; onLang: (l: Lang) => void;
  hasEnglish: boolean; canShare: boolean; hasDownloads: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-3 rounded-2xl bg-surface px-4 py-3 print:hidden">
      <AudienceSwitch value={audience} onChange={onAudience} lang={lang} />
      <div className="flex flex-wrap items-center gap-2">
        {original === "th" && hasEnglish && (
          <div role="group" aria-label={L(lang, T.reportLanguage)} className="flex gap-1.5">
            {(["th", "en"] as const).map((l) => (
              // each language names itself in its own script (and is spoken in it)
              <button key={l} type="button" lang={l} aria-pressed={lang === l} onClick={() => onLang(l)} className="rchip">{LANGUAGE_NAME[l]}</button>
            ))}
          </div>
        )}
        {hasDownloads && <a href="#h-downloads" className="rbtn">{L(lang, T.download)}</a>}
        <button type="button" onClick={() => window.print()} className="rbtn">{L(lang, T.print)}</button>
        {canShare && <CopyLinkButton lang={lang} />}
      </div>
    </div>
  );
}

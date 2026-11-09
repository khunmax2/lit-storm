"use client";

import { Fragment } from "react";
import { EXCLUSION_REASON_LABEL } from "@mra/lib/charts-data";
import { citationParts, vancouver, type CitationId } from "@mra/lib/citation";
import type { Lang } from "@mra/lib/i18n";
import { fieldLang, RC } from "@mra/lib/i18n-report";
import type { ExclusionReason, Paper, Stats } from "@mra/lib/types";
import { CopyTextButton } from "../ui/copy-text";
import { DisclosureChevron } from "../ui/disclosure-chevron";
import type { Select } from "./report-parts";
import { L, Lw } from "./text";

const R = RC.refs;

const ID_NAME: Record<CitationId["label"], string> = { doi: "DOI", PMID: "PubMed", PMCID: "PubMed Central", ThaiJO: "ThaiJO" };

/** The anchor of a paper's reference (`#ref-P3`): the source rail links here. */
export const referenceId = (ref: string): string => `ref-${ref}`;

/** The reference text with its identifiers as links (doi.org, PubMed, PubMed Central, the ThaiJO page); the text is
 * never translated. Also the quick answer's reference list (Plan 27). */
export function CitationText({ paper, lang, small = false }: { paper: Paper; lang: Lang; small?: boolean }) {
  const { text, ids, segments } = citationParts(paper);
  const opens = L(lang, R.newTab);
  return (
    // the reference is written as published (Vancouver, the title in its own language)
    <p data-citation className={small ? "inline break-words" : "max-w-[75ch] text-[0.95rem] leading-[1.7] break-words"} lang={fieldLang(text.join(" "), lang)}>
      {segments.map((s, i) => (
        <Fragment key={i}>{i > 0 && " "}{s.isolate ? <bdi>{s.text}</bdi> : s.text}</Fragment>
      ))}
      {ids.map((id) => (
        <span key={id.label}>
          {" "}{id.label}:{" "}
          <a href={id.href} target="_blank" rel="noreferrer" aria-label={`${ID_NAME[id.label]} ${id.value} ${opens}`}
            className={`underline underline-offset-2 [overflow-wrap:anywhere] ${small ? "" : "text-primary"}`}>
            {/* a break opportunity after each "/" (DOIs): the value wraps there first, mid-value only if it must */}
            {id.value.split("/").map((seg, i) => <Fragment key={i}>{i > 0 && <>/<wbr /></>}{seg}</Fragment>)}
          </a>.
        </span>
      ))}
    </p>
  );
}

function Reference({ paper, lang, onSelect, related = [], nested = false }: {
  paper: Paper; lang: Lang; onSelect: Select;
  /** further reports of the same trial, listed under this primary reference */
  related?: Paper[];
  /** this is a further report under its primary */
  nested?: boolean;
}) {
  return (
    // focusable as the target of `#ref-Pn`: following the rail's link puts focus on the reference itself
    <li id={referenceId(paper.ref)} data-reference={paper.ref} tabIndex={-1}
      className={`group mb-2 break-inside-avoid outline-none scroll-mt-[calc(var(--header-h)+env(safe-area-inset-top,0px)+3.5rem)] ${nested ? "mt-2 border-t border-dashed border-rule pt-2" : ""}`}>
      {nested && <span data-related-label className="label mb-0.5 block w-fit nw">{L(lang, R.related)}</span>}
      <div className="flex flex-wrap items-baseline gap-x-1">
        <button type="button" onClick={() => onSelect(paper.ref)} aria-label={L(lang, RC.parts.open(paper.ref))}
          className="font-semibold text-primary hover:underline">{paper.ref}</button>
        <div className="min-w-0 flex-1 basis-[80%]">
          <CitationText paper={paper} lang={lang} small />{" "}
          <CopyTextButton quiet className="inline-flex [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:focus-within:opacity-100"
            text={vancouver(paper)} label={L(lang, R.copy)} name={L(lang, R.copyRef(paper.ref))} copied={L(lang, R.copied)}
            failed={L(lang, R.copyFailed)} boxLabel={L(lang, R.copyBox(paper.ref))} />
        </div>
      </div>
      {paper.design_excluded && <p data-reference-note="design_excluded" className="text-muted">{L(lang, R.designExcluded)}</p>}
      {paper.verification?.design_mismatch && <p data-reference-note="design_mismatch" className="text-muted">{L(lang, R.designMismatch)}</p>}
      {related.length > 0 && (
        <ul aria-label={L(lang, R.relatedOf(paper.ref))}>
          {related.map((r) => <Reference key={r.ref} paper={r} lang={lang} onSelect={onSelect} nested />)}
        </ul>
      )}
    </li>
  );
}

/**
 * Numbered references in P-number order (Plan 20 Task 6), every paper whatever the filters. A further report of a trial
 * (Task 10) is listed under its primary reference, not as a study of its own. One interaction everywhere: a study
 * code opens the paper in the source rail, and the rail links back here (`#ref-Pn`).
 */
export function ReferenceList({ papers, lang, onSelect }: { papers: Paper[]; lang: Lang; onSelect: Select }) {
  const refs = new Set(papers.map((p) => p.ref));
  const under = new Map<string, Paper[]>();
  for (const p of papers) {
    if (p.related_to && refs.has(p.related_to)) under.set(p.related_to, [...(under.get(p.related_to) ?? []), p]);
  }
  return (
    <ol aria-label={L(lang, R.list)} className="text-[12px] leading-[1.6] text-muted [column-gap:32px] [columns:2_440px]">
      {papers.filter((p) => !(p.related_to && refs.has(p.related_to))).map((p) => (
        <Reference key={p.ref} paper={p} lang={lang} onSelect={onSelect} related={under.get(p.ref)} />
      ))}
    </ol>
  );
}

const REASONS = Object.keys(EXCLUSION_REASON_LABEL) as ExclusionReason[];

/**
 * Records excluded at screening, with their reasons. The result keeps only the reason counts
 * (`stats.excluded_screening`), not the records, so the disclosure shows the counts and says so. Null without them.
 */
export function ExcludedAtScreening({ stats, lang }: { stats?: Stats | null; lang: Lang }) {
  const reasons = stats?.excluded_screening;
  if (!reasons) return null;
  const rows = REASONS.filter((k) => (reasons[k] ?? 0) > 0).map((k) => ({ k, n: reasons[k] as number }));
  const total = rows.reduce((s, r) => s + r.n, 0);
  const caption = L(lang, R.excludedCaption);
  return (
    <details data-excluded-screening className="group text-[0.92rem]">
      <summary className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 font-display font-semibold text-primary md:min-h-0">
        <DisclosureChevron />
        {L(lang, R.excluded(total))}
      </summary>
      <div className="mt-2 grid gap-2">
        {rows.length ? (
          <table className="w-full max-w-[36rem] border-collapse text-[0.9rem]">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr className="border-b border-rule">
                <th scope="col" className="py-1.5 pr-3 text-left label">{L(lang, R.reason)}</th>
                <th scope="col" className="py-1.5 text-right label">{L(lang, R.records)}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.k} className="border-b border-rule">
                  <th scope="row" className="py-1.5 pr-3 text-left font-body font-normal">{EXCLUSION_REASON_LABEL[r.k][lang]}</th>
                  <td className="py-1.5 text-right font-display tabular-nums">{r.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="text-muted">{L(lang, R.noReason)}</p>}
        <p className="max-w-[65ch] text-[0.85rem] text-muted">{L(lang, R.excludedNote)}</p>
      </div>
    </details>
  );
}

/** The last thing on the page: references, then the records excluded at screening. In-text citations are unchanged. */
export function ReferencesSection({ papers, stats, lang, onSelect }: {
  papers: Paper[]; stats?: Stats | null; lang: Lang; onSelect: Select;
}) {
  return (
    <section aria-labelledby="h-papers" className="grid min-w-0 gap-2 border-t border-rule px-1 pt-3">
      <h2 id="h-papers" className="scroll-mt-[calc(var(--header-h)+env(safe-area-inset-top,0px)+3.5rem)] text-[14px] font-semibold text-muted">
        {Lw(lang, R.h2)} <span className="font-normal">{L(lang, RC.refs.count(papers.length))} · {L(lang, R.style)}</span>
      </h2>
      <ReferenceList papers={papers} lang={lang} onSelect={onSelect} />
      <ExcludedAtScreening stats={stats} lang={lang} />
    </section>
  );
}

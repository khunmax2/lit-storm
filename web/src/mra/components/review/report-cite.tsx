"use client";

import type { ReactNode } from "react";
import { howToCite, howToCiteParts } from "@mra/lib/citation";
import { reviewCsv } from "@mra/lib/export-csv";
import type { Lang } from "@mra/lib/i18n";
import { fieldLang, RC, type Pair } from "@mra/lib/i18n-report";
import type { ReviewTypeOrLegacy } from "@mra/lib/review-type";
import type { Review, ReviewResult } from "@mra/lib/types";
import { CopyTextButton } from "../ui/copy-text";
import { SECTION_H2 as H2, SECTION_H3 as H3 } from "./report-nav";
import { L, Lw } from "./text";

const C = RC.cite;

/** The refined question as the title block shows it (the H1). */
export function citedQuestion(review: Review, result: ReviewResult, lang: Lang): string {
  const q = result.question;
  const text = lang === "en" && q?.english ? q.english : q;
  return text?.refined_question || (lang === "en" ? q?.english_topic : null) || q?.original_topic || review.topic;
}

/** A download the page around the report provides (DeepLit keeps the review; MRA's own routes are not there). */
export interface ReportDownload { name: string; ext: string; what: Pair; href: string }

/**
 * The downloads as a labelled list (format and what each file holds; sizes are not known before the file is made, so
 * none is claimed). The CSV is made here from the review.
 */
function Downloads({ result, links, id, lang }: { result: ReviewResult; links: ReportDownload[]; id: string; lang: Lang }) {
  function saveCsv() {
    const url = URL.createObjectURL(new Blob([reviewCsv(result)], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `mra-review-${id.slice(0, 8)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
  const Row = ({ name, what, children }: { name: string; what: string; children?: ReactNode }) => (
    <span className="min-w-0"><b className="font-semibold">{children ?? name}</b> <span className="text-muted">{what}</span></span>
  );
  return (
    <ul aria-label={L(lang, C.list)} className="grid text-[13px] leading-[1.5]">
      {links.map((d) => (
        <li key={d.ext} className="border-t border-rule py-1.5 first:border-t-0">
          <Row name={d.name} what={L(lang, d.what)}><a href={d.href} download className="text-primary underline underline-offset-2">{d.name}</a></Row>
        </li>
      ))}
      <li className="border-t border-rule py-1.5 first:border-t-0">
        <Row name="CSV" what={L(lang, C.csv)}><button type="button" onClick={saveCsv} className="font-semibold text-primary underline underline-offset-2">CSV</button></Row>
      </li>
    </ul>
  );
}

/**
 * How to cite this report, and the downloads. The date is when the review finished (or was created), never the viewing
 * time. Without `links`, only how to cite. The citation has no URL here: the report lives inside the owner's DeepLit.
 */
export function DownloadsAndCite({ review, result, type, lang, links }: {
  review: Review; result: ReviewResult; type: ReviewTypeOrLegacy; lang: Lang; links?: ReportDownload[];
}) {
  const cite = howToCite({ question: citedQuestion(review, result, lang), type, id: review.id,
    date: review.finished_at ?? review.created_at, url: null, lang });
  const citeParts = howToCiteParts({ question: citedQuestion(review, result, lang), type, id: review.id,
    date: review.finished_at ?? review.created_at, url: null, lang });
  const R = RC.refs;
  return (
    <section aria-labelledby="h-downloads" className="grid gap-3">
      <h2 id="h-downloads" className={H2}>{Lw(lang, links ? C.h2 : C.title)}</h2>
      <div className="rrow gap-7">
        <div className="rrow-main grid content-start gap-2">
          {links && <h3 id="cite-report" className={H3}>{Lw(lang, C.title)}</h3>}
          <p data-how-to-cite className="text-[13px] leading-[1.65] break-words text-muted" lang={fieldLang(cite, lang)}>
            {citeParts.map((s, i) => (s.isolate ? <bdi key={i}>{s.text}</bdi> : s.text))}
          </p>
          <CopyTextButton text={cite} label={L(lang, R.copy)} name={L(lang, C.name)} copied={L(lang, R.copied)}
            failed={L(lang, R.copyFailed)} boxLabel={L(lang, C.box)} />
        </div>
        {links && <div className="print:hidden"><Downloads result={result} links={links} id={review.id} lang={lang} /></div>}
      </div>
    </section>
  );
}

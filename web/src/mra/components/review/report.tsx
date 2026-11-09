"use client";

import Link from "next/link";
import { Fragment, useId, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { audienceLayout, DEFAULT_AUDIENCE, learnerNoteAfter, opensRationale, type Audience } from "@mra/lib/audience";
import { conceptTree } from "@mra/lib/concept-map";
import { emptyFilters, filterPapers, isFiltered, isPooled, themePapers, type Filters } from "@mra/lib/charts-data";
import { EMPTY_MAP, evidenceMap } from "@mra/lib/evidence-map";
import type { Lang } from "@mra/lib/i18n";
import { fieldLang, RC, type Pair } from "@mra/lib/i18n-report";
import { robSummary } from "@mra/lib/rob-summary";
import { alignMarkers } from "@mra/lib/support";
import { cellOutcome, keyFindingViews, sameModelReadings, sofRows, type OutcomeContext } from "@mra/lib/report-view";
import {
  isGraded, metaPoolGap, reviewTypeOf, SECTION_ANCHOR, showsDirection, showsRiskOfBias, showsSection,
  type BlockId, type TopSectionId,
} from "@mra/lib/review-type";
import type { ComparisonRow, Paper, Review } from "@mra/lib/types";
import { printPageCss } from "@mra/lib/print";
import { VerifiedAppendix } from "./appendix";
import { LearnerNote, ReportNotices } from "./audience";
import { ReadingCard } from "./bottom-line";
import { PrintMode, usePrintSetup } from "./print-mode";
import { chartsContent } from "@mra/lib/charts-content";
import { Charts, hasForestCard, StudyMap } from "./charts";
import { CitationNetworkSection } from "./citation-network";
import { ConceptMapSection } from "./concept-map";
import { EvidenceMapSection } from "./evidence-map";
import { KeyFindings } from "./key-findings";
import { Limitations } from "./limitations";
import { LitMatrixSection, StudyTiles } from "./lit-matrix";
import { MetaAnalysisSection } from "./meta-analysis";
import { FilterBar, FilterStatus } from "./filter-bar";
import {
  CitedText, ClaimsPanel, ComparisonMatrix, hasCheckedMark, MatrixLegend, QuestionDetails, READING, SameModelReadings, SupportLegend, type MarkerSupport,
} from "./report-parts";
import { ReferencesSection } from "./references";
import { citedQuestion, DownloadsAndCite, type ReportDownload } from "./report-cite";
import { MethodsSection } from "./methods-section";
import { PrismaFlow } from "./prisma-flow";
import { RobSummarySection } from "./rob-summary";
import { ReportChapters, SECTION_H2 as H2, SectionHeading, Subsections } from "./report-nav";
import { RailDrawer } from "./rail-drawer";
import { SofTable } from "./sof-table";
import { SourceRail } from "./source-rail";
import { AnswerBand, PicoCards, ReportToolbar } from "./report-head";
import { L, Lw } from "./text";
import { byId } from "@mra/lib/host";
import { chapters, type TocEntry } from "@mra/lib/report-toc";

type Selection = { ref: string; outcome?: string; claim?: string };

/** Map a matrix cell to the paper outcome it came from (by finding text, then by direction, then the first). */
function outcomeFor(paper: Paper | undefined, row: ComparisonRow, ref: string): string | undefined {
  return cellOutcome(paper, row, ref)?.en.outcome;
}

/** Top-level sections: anchor id, short table-of-contents label and the H2 of a group section. */
const N = RC.nav;
const TOP: Record<Exclude<TopSectionId, "title">, { id: string; nav: Pair; h2?: Pair }> = {
  bottom_line: { id: SECTION_ANCHOR.bottom_line, nav: N.answer },
  key_findings: { id: SECTION_ANCHOR.key_findings, nav: N.keyFindings },
  sof: { id: SECTION_ANCHOR.sof, nav: N.sof },
  selection: { id: SECTION_ANCHOR.selection, nav: N.selection, h2: N.selectionH2 },
  characteristics: { id: SECTION_ANCHOR.characteristics, nav: N.characteristics, h2: N.characteristicsH2 },
  results: { id: SECTION_ANCHOR.results, nav: N.results, h2: N.resultsH2 },
  rob: { id: SECTION_ANCHOR.rob, nav: N.rob },
  consistency: { id: SECTION_ANCHOR.consistency, nav: N.consistency, h2: N.consistencyH2 },
  landscape: { id: SECTION_ANCHOR.landscape, nav: N.landscape, h2: N.landscapeH2 },
  limitations: { id: SECTION_ANCHOR.limitations, nav: N.limitations },
  gaps: { id: SECTION_ANCHOR.gaps, nav: N.gaps },
  discussion: { id: SECTION_ANCHOR.discussion, nav: N.discussion },
  methods: { id: SECTION_ANCHOR.methods, nav: N.methods },
  references: { id: SECTION_ANCHOR.references, nav: N.references },
  downloads: { id: SECTION_ANCHOR.downloads, nav: N.downloads },
  appendix: { id: SECTION_ANCHOR.appendix, nav: N.appendix },
};

/** Sections that share a row when the page puts them next to each other. */
const SIDE_BY_SIDE: [TopSectionId, TopSectionId][] = [["rob", "consistency"], ["discussion", "gaps"]];

/**
 * The page speaks the report's language (Plan 20 Task 7): `<html lang>` follows the language shown (the site header and
 * footer read it), and goes back to what it was when the report closes. A layout effect: set before the first paint, so
 * an English report never shows a Thai header for a frame (fix round 1).
 */
export function useDocumentLang(lang: Lang) {
  useLayoutEffect(() => {
    void lang; // DeepLit: the report's own lang attribute is enough; the app's <html lang> stays the app's
  }, [lang]);
}

/**
 * The report (answer-first order, from SECTIONS_BY_TYPE), DeepLit's layout: the answer in a band across the page, PICO, the
 * audience and language, then the sections as cards on the ground, the chapter list beside them from `lg`, the references
 * last of all, the source rail floating over the page while a paper is open.
 * offline: no links back to MRA's own routes. downloads: what the page around the report offers instead.
 * Plan 26: `initialAudience` (default public) picks the presentation (lib/audience.ts: section order, notes, what starts
 * open); the switch under the title changes it and reports the choice through `onAudience`. The content never changes.
 */
export function Report({ review, offline = false, initialAudience, onAudience, downloads }: {
  review: Review; offline?: boolean; initialAudience?: Audience; onAudience?: (audience: Audience) => void;
  downloads?: ReportDownload[];
}) {
  const result = useMemo(() => review.result ?? {}, [review.result]);
  const original = (result.language ?? review.language ?? "th") as Lang;
  const [lang, setLang] = useState<Lang>(original);
  useDocumentLang(lang);
  const [audience, setAudience] = useState<Audience>(initialAudience ?? DEFAULT_AUDIENCE);
  function changeAudience(next: Audience) {
    setAudience(next);
    onAudience?.(next);
  }
  const showEn = lang === "en" && original === "th";
  const synthesis = (showEn ? result.synthesis_en : result.synthesis) ?? result.synthesis ?? { executive_summary: result.summary ?? "" };
  const papers = useMemo(() => result.papers ?? [], [result.papers]);
  const byRef = useMemo(() => new Map(papers.map((p) => [p.ref, p])), [papers]);
  const refs = useMemo(() => new Set(papers.map((p) => p.ref)), [papers]);
  const pooledRefs = useMemo(() => new Set(papers.filter(isPooled).map((p) => p.ref)), [papers]);
  const rows = useMemo(() => (synthesis.comparison?.length ? synthesis.comparison : showEn ? result.synthesis?.comparison ?? [] : []), [synthesis.comparison, showEn, result.synthesis?.comparison]);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const visible = useMemo(() => filterPapers(papers, filters), [papers, filters]);
  const matrixRefs = useMemo(() => visible.filter((p) => rows.some((r) => r.cells.some((c) => c.ref === p.ref))).map((p) => p.ref), [visible, rows]);
  const visibleRows = useMemo(() => rows.filter((r) => r.cells.some((c) => matrixRefs.includes(c.ref))), [rows, matrixRefs]);
  const type = reviewTypeOf(result);
  const poolGap = metaPoolGap(result);
  const map = useMemo(() => (showsSection(type, "evidence_map") ? evidenceMap(visible, rows, lang) : EMPTY_MAP), [type, visible, rows, lang]);
  // Built from the filtered papers, like the lit matrix and the evidence map; null where the type has no concept map.
  const tree = useMemo(
    () => (showsSection(type, "concept_map") ? conceptTree({ ...result, papers: visible }, lang, type) : null),
    [type, result, visible, lang],
  );
  // The rail starts empty (Plan 20): nothing is pre-selected until the reader picks a number or a study.
  const [selection, setSelection] = useState<Selection | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const active = selection;

  const railHeading = useId();
  const root = useRef<HTMLDivElement>(null);
  // Plan 20 Task 8: print mode (every disclosure open, tables instead of cards, light charts at paper width)
  const printing = usePrintSetup(root);
  const returnFocus = useRef<HTMLElement | null>(null);
  const pressed = useRef<HTMLElement | null>(null);

  /** Safari (iOS and macOS) does not focus a tapped button, so remember what was pressed as the fallback trigger. */
  function notePress(e: { target: EventTarget | null }) {
    const el = e.target instanceof Element ? e.target.closest("button,a,[tabindex]") : null;
    pressed.current = el instanceof HTMLElement ? el : null;
  }

  function select(ref: string, outcome?: string, claim?: string) {
    const focused = document.activeElement;
    returnFocus.current = focused instanceof HTMLElement && focused !== document.body ? focused : pressed.current;
    setSelection({ ref, outcome, claim });
    setDrawerOpen(true);
  }

  /**
   * The rail's "see in the references" link (Plan 20 Task 6): the anchor jumps to `#ref-Pn`, which takes focus; the
   * drawer (narrow screens) closes and hands focus to that reference too, instead of the code that opened it.
   */
  function toReference(ref: string) {
    const target = byId(`ref-${ref}`);
    if (target) returnFocus.current = target;
    setDrawerOpen(false);
  }

  // Key findings and the summary of findings use every paper (the filters narrow the tables and charts below them).
  const ctx = useMemo<OutcomeContext>(() => ({
    rows, enRows: result.synthesis_en?.comparison ?? [], papers, meta: result.meta_analysis, lang,
  }), [rows, result.synthesis_en?.comparison, papers, result.meta_analysis, lang]);
  const findings = useMemo(() => keyFindingViews(synthesis.key_findings ?? [], result.synthesis_en?.key_findings, ctx),
    [synthesis.key_findings, result.synthesis_en?.key_findings, ctx]);
  const graded = isGraded(type) && synthesis.evidence_strength != null;
  const sof = useMemo(() => (showsSection(type, "sof") ? sofRows(synthesis.key_findings ?? [], result.synthesis_en?.key_findings, ctx, graded ? synthesis.evidence_strength : null) : []),
    [type, synthesis.key_findings, result.synthesis_en?.key_findings, ctx, graded, synthesis.evidence_strength]);

  const hasPapers = papers.length > 0;
  // The results figures follow the filters (like the matrix): built from the visible papers.
  const charts = useMemo(() => chartsContent(result, visible, rows, result.synthesis_en?.comparison ?? [], lang),
    [result, visible, rows, lang]);
  // The risk-of-bias summary (Plan 20 Task 4) uses every paper, like the summary of findings; none for scoping.
  const hasRob = useMemo(() => showsSection(type, "rob") && showsRiskOfBias(type) && robSummary(papers, lang) != null, [type, papers, lang]);
  const answer = synthesis.answer?.trim() ?? "";
  const discussion = synthesis.executive_summary || result.summary || "";
  // Plan 25: the summary's citation groups tied to the English claims the engine checked (no badge when they moved)
  const support = result.support ?? null;
  const discussionMarks = useMemo<MarkerSupport | null>(() => (support
    ? { claims: alignMarkers(discussion, support), papers: byRef, lang } : null), [support, discussion, byRef, lang]);
  const hasClaims = showsSection(type, "claims") && !!(synthesis.consensus?.length || synthesis.conflicts?.length);
  const hasMatrix = showsSection(type, "findings") && rows.length > 0;
  const hasLitMatrix = showsSection(type, "lit_matrix") && hasPapers;
  // Plan 14b: drawn only when the citation step ran (result.citations is null for legacy results and skipped steps).
  const citations = result.citations ?? null;
  const hasCitations = showsSection(type, "citations") && !!citations && hasPapers;
  const hasConceptMap = !!tree && tree.leaves > 0;
  const hasEvidenceMap = showsSection(type, "evidence_map") && (map.byConcept.rows.length > 0 || map.byYear.rows.length > 0);
  // A meta review with no papers renders the "Try this" block: nothing could be pooled, an empty pooled section (with its
  // banner) would only repeat that there are no studies.
  const hasMeta = showsSection(type, "meta") && hasPapers;
  // The pool's outcome is an English matrix row: directions come from the English rows (the shown ones for an English review).
  const metaRows = result.synthesis_en?.comparison?.length ? result.synthesis_en.comparison : result.synthesis?.comparison ?? [];
  const filterStatus = <FilterStatus filters={filters} onChange={setFilters} shown={visible.length} total={papers.length} lang={lang} />;

  const blocks: Record<BlockId, { show: boolean; node: ReactNode }> = {
    // The flow counts every record of the search (result.stats), so the filters do not apply to it; it shows even when no
    // study was included, since then it explains the empty result.
    prisma: { show: showsSection(type, "prisma") && !!result.stats,
      node: <PrismaFlow stats={result.stats} methods={result.methods} options={review.options} type={type} lang={lang}
        heading={<h2 id={TOP.selection.id} className={H2}>{Lw(lang, N.selectionH2)}</h2>} /> },
    evidence_map: { show: hasEvidenceMap, node: <EvidenceMapSection map={map} lang={lang} /> },
    lit_matrix: { show: hasLitMatrix, node: (
      <LitMatrixSection papers={visible} allPapers={papers} lang={lang} type={type} onSelect={select} reviewId={review.id} offline={offline}
        citations={citations} question={result.question} selected={active?.ref} />
    ) },
    findings: { show: hasMatrix, node: (
      <section aria-labelledby="h-matrix" className="grid grid-cols-[minmax(0,1fr)] gap-3">
        <SectionHeading id="h-matrix">{L(lang, RC.report.findingsByStudy)}</SectionHeading>
        {visibleRows.length ? <ComparisonMatrix rows={visibleRows} refs={matrixRefs} papers={papers} lang={lang} onSelect={select} selected={active ?? undefined}
          pooledRefs={pooledRefs}
          outcomeOf={(row, ref) => outcomeFor(byRef.get(ref), row, ref)} /> : <p className="text-[0.9rem] text-muted">{L(lang, RC.report.noMatch)}</p>}
        <MatrixLegend lang={lang} themes={themePapers(papers).length > 0} />
      </section>
    ) },
    forest: { show: hasPapers && showsSection(type, "forest") && !charts.empty, node: null },
    meta: { show: hasMeta, node: (
      <MetaAnalysisSection meta={result.meta_analysis} papers={papers} rows={metaRows} lang={lang} english={lang === "en"}
        filtered={isFiltered(filters)} quality={result.quality} onSelect={select} />
    ) },
    claims: { show: hasClaims, node: <ClaimsPanel consensus={synthesis.consensus ?? []} conflicts={synthesis.conflicts ?? []} lang={lang} onSelect={select} refs={refs}
      graded={graded} /> },
    concept_map: { show: hasConceptMap, node: tree && <ConceptMapSection tree={tree} lang={lang} onSelect={select} /> },
    citations: { show: hasCitations, node: citations && <CitationNetworkSection citations={citations} papers={visible} lang={lang} onSelect={select} /> },
  };

  const layout = audienceLayout(type, audience);
  const sections: { id: TopSectionId; node: ReactNode; card: boolean }[] = [];
  for (const { id, blocks: ids } of layout) {
    if (id === "title") continue;
    const meta = TOP[id];
    const shown = ids.filter((b) => blocks[b].show);
    if (meta.h2) {
      if (!shown.length) continue;
      sections.push({ id, ...groupSection(id, shown) });
      continue;
    }
    const node = sectionNode(id);
    if (node) sections.push({ id, node, card: id !== "key_findings" && id !== "references" });
  }

  /** A group section: on the ground with a card per figure (results, landscape), or one card (the others). */
  function groupSection(id: Exclude<TopSectionId, "title">, shown: BlockId[]): { node: ReactNode; card: boolean } {
    const meta = TOP[id];
    const heading = meta.h2 && <h2 id={meta.id} className={H2}>{Lw(lang, meta.h2)}</h2>;
    if (id === "selection") return { card: true, node: <>{shown.map((b) => <Fragment key={b}>{blocks[b].node}</Fragment>)}</> };
    if (id === "results") {
      const forest = shown.includes("forest");
      const matrix = shown.includes("findings");
      const studyMap = forest && !!charts.map;
      return { card: false, node: (
        <section aria-labelledby={meta.id} className="rstack">
          <h2 id={meta.id} className={`${H2} ground-h2`}>{Lw(lang, meta.h2!)}</h2>
          {filterStatus}
          <Subsections>
            {(matrix || studyMap) && (
              <div className="rrow">
                {matrix && <div className="rc flex-[1_1_440px]">{blocks.findings.node}</div>}
                {studyMap && <div className="rc flex-[999_1_400px]"><StudyMap content={charts} lang={lang} onSelect={select} /></div>}
              </div>
            )}
            {forest && hasForestCard(charts) && <div className="rc"><Charts content={charts} result={result} lang={lang} onSelect={select} /></div>}
            {shown.includes("meta") && <div className="rc">{blocks.meta.node}</div>}
          </Subsections>
        </section>
      ) };
    }
    if (id === "landscape") {
      return { card: false, node: (
        <section aria-labelledby={meta.id} className="rstack">
          <h2 id={meta.id} className={`${H2} ground-h2`}>{Lw(lang, meta.h2!)}</h2>
          <Subsections>
            <div className="rrow">
              {shown.includes("concept_map") && <div className="rc">{blocks.concept_map.node}</div>}
              {/* the network needs the width: it takes a row of its own until there is room for both */}
              {shown.includes("citations") && <div className="rc flex-[999_1_720px]">{blocks.citations.node}</div>}
            </div>
          </Subsections>
        </section>
      ) };
    }
    if (id === "characteristics") {
      return { card: true, node: (
        <section aria-labelledby={meta.id} className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3.5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            {heading}
            {papers.length > 1 && <span className="text-[13px] text-muted">{L(lang, RC.filter.shown(visible.length, papers.length))}</span>}
          </div>
          <StudyTiles papers={visible} lang={lang} type={type} citations={citations} onSelect={select} selected={active?.ref} />
          {papers.length > 1 && <FilterBar papers={papers} filters={filters} onChange={setFilters} lang={lang} showRisk={showsRiskOfBias(type)} showDirection={showsDirection(type)} />}
          <Subsections>{shown.map((b) => <Fragment key={b}>{blocks[b].node}</Fragment>)}</Subsections>
        </section>
      ) };
    }
    return { card: true, node: (
      <section aria-labelledby={meta.id} className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
        {heading}
        {shown.map((b) => <Fragment key={b}>{blocks[b].node}</Fragment>)}
      </section>
    ) };
  }

  function sectionNode(id: TopSectionId): ReactNode {
    switch (id) {
      case "bottom_line":
        return <ReadingCard synthesis={synthesis} result={result} papers={papers} lang={lang} english={lang === "en"} openRationale={opensRationale(audience)}
          notices={<ReportNotices result={result} audience={audience} lang={lang} hasPapers={hasPapers} />}
          question={<QuestionDetails question={result.question} lang={lang} type={type} />} />;
      case "key_findings":
        return hasPapers && findings.length ? <KeyFindings findings={findings} lang={lang} onSelect={select} support={support} papers={byRef} /> : null;
      case "sof":
        return hasPapers && sof.length ? <SofTable rows={sof} lang={lang} onSelect={select} graded={graded} /> : null;
      case "limitations":
        return hasPapers ? <Limitations result={result} type={type} lang={lang} /> : null;
      case "gaps":
        return synthesis.research_gaps?.length ? (
          <section aria-labelledby="h-gaps" className="grid gap-3">
            <h2 id="h-gaps" className={H2}>{Lw(lang, RC.report.gapsH2)}</h2>
            <ol className="grid list-decimal gap-2.5 pl-5 text-[14px] leading-[1.65]">
              {synthesis.research_gaps.map((g) => <li key={g} lang={fieldLang(g, lang)}>{g}</li>)}
            </ol>
          </section>
        ) : null;
      case "discussion":
        // With a direct answer, the long model summary becomes the discussion; without one it already led the report.
        return hasPapers && answer && discussion && discussion.trim() !== answer ? (
          <section aria-labelledby="h-discussion" className="grid gap-3">
            <h2 id="h-discussion" className={H2}>{Lw(lang, RC.report.discussionH2)}</h2>
            <p className={`max-w-[74ch] ${READING}`} data-prose lang={fieldLang(discussion, lang)}><CitedText text={discussion} onSelect={select} refs={refs} support={discussionMarks} /></p>
            <p className="text-[12px] text-muted">{L(lang, RC.report.discussionNote)}</p>
            {hasCheckedMark(discussionMarks) && <SupportLegend lang={lang} />}
          </section>
        ) : null;
      case "rob":
        return hasRob ? <RobSummarySection papers={papers} type={type} lang={lang} fullText={result.stats?.with_fulltext != null} /> : null;
      case "methods":
        return <MethodsSection review={review} result={result} type={type} lang={lang} />;
      case "references":
        // Plan 20 Task 6: a complete reference list (the filters do not apply) and the records excluded at screening
        return hasPapers ? <ReferencesSection papers={papers} stats={result.stats} lang={lang} onSelect={select} /> : null;
      case "downloads":
        return <DownloadsAndCite review={review} result={result} type={type} lang={lang} links={downloads} />;
      case "appendix":
        // Plan 20 Task 8: every verified number with its source sentence (collapsed on screen, open in print)
        return hasPapers ? <VerifiedAppendix papers={papers} meta={result.meta_analysis} metaRows={metaRows} lang={lang} onSelect={select}
          verifyQuotes={result.methods?.extraction?.verify_quotes !== false} /> : null;
      default:
        return null;
    }
  }

  // With no study included (Plan 20 Task 7), the selection flow explains the empty result: it comes right after the
  // answer, before "Try this", and the short section list stays so the page still has a structure.
  const lead = hasPapers ? 1 : Math.max(1, sections.findIndex((s) => s.id === "selection") + 1);
  const entries: TocEntry[] = sections.map(({ id }) => {
    const top = TOP[id as Exclude<TopSectionId, "title">];
    return { section: id, id: top.id, label: L(lang, !downloads && id === "downloads" ? N.offlineDownloads : top.nav) };
  });
  if (!hasPapers) entries.splice(lead, 0, { section: "try_this", id: "h-next", label: L(lang, N.tryThis) });
  const contents = chapters(entries);

  // A section as it stands on the page: its card with the learner's note inside; two that belong together share a row.
  const placed = (s: { id: TopSectionId; node: ReactNode; card: boolean }, wide = false) => {
    const note = learnerNoteAfter(audience, s.id);
    const noteNode = note ? <LearnerNote id={note} lang={lang} /> : null;
    if (s.id === "bottom_line") return s.node; // the reading card is its own card
    return s.card ? <div className={wide ? "rc rrow-main" : "rc"}>{s.node}{noteNode}</div> : <>{s.node}{noteNode}</>;
  };
  const stand = (list: typeof sections) => {
    const out: ReactNode[] = [];
    for (let i = 0; i < list.length; i += 1) {
      const next = list[i + 1];
      const pair = next && SIDE_BY_SIDE.some(([a, b]) => a === list[i].id && b === next.id);
      if (pair) {
        out.push(<div key={list[i].id} className="rrow">{placed(list[i], true)}{placed(next)}</div>);
        i += 1;
      } else {
        out.push(<Fragment key={list[i].id}>{placed(list[i])}</Fragment>);
      }
    }
    return out;
  };

  // The running header and footer of a printout: @page margin boxes (where the browser draws them)
  const pageCss = printPageCss({ title: citedQuestion(review, result, lang), id: review.id.slice(0, 8), lang });
  return (
    <PrintMode.Provider value={printing}>
    <SameModelReadings.Provider value={sameModelReadings(result)}>
    <div ref={root} className="mx-auto grid max-w-[1680px] grid-cols-[minmax(0,1fr)] gap-4 px-4 pt-7 pb-14 sm:px-6 lg:grid-cols-[minmax(0,1fr)_max-content] lg:items-start lg:gap-x-5 print:block print:p-0"
      onPointerDownCapture={notePress} onClickCapture={notePress}
      style={offline ? ({ "--header-h": "var(--mra-header-h, 0px)" } as CSSProperties) : undefined} data-report lang={lang} data-printing={printing || undefined}>
      <style data-print-page>{pageCss}</style>
      <AnswerBand review={review} result={result} synthesis={synthesis} type={type} lang={lang} papers={papers} refs={refs}
        marks={answer ? null : discussionMarks} poolGap={poolGap} onSelect={select} />
      <ReportChapters chapters={contents} label={L(lang, N.contents)} lang={lang} />
      <div className="rstack lg:col-start-1 lg:row-start-2">
        <PicoCards question={result.question} lang={lang} />
        <ReportToolbar audience={audience} onAudience={changeAudience} lang={lang} original={original} onLang={setLang}
          hasEnglish={!!result.synthesis_en} canShare={!offline || !!downloads} hasDownloads={!!downloads} />

        {stand(sections.slice(0, lead))}

        {!hasPapers && (
          <section aria-labelledby="h-next" className="rc">
            <h2 id="h-next" className={H2}>{Lw(lang, RC.report.tryThisH2)}</h2>
            <ul className={`grid list-disc gap-1.5 pl-5 ${READING}`}>
              <li>{L(lang, RC.report.tryEnglish)}</li>
              <li>{L(lang, RC.report.tryBroader)}</li>
            </ul>
            {/* the offline file has no links back to the service: "/" there is the file-system root (final review M3) */}
            {!offline && (
              <Link href="/" className="w-fit rounded-sm border border-primary bg-primary px-4 py-2 font-display font-semibold text-on-primary no-underline hover:brightness-110">
                {L(lang, RC.report.askNew)}
              </Link>
            )}
          </section>
        )}

        {stand(sections.slice(lead))}
      </div>

      {hasPapers && (
        <RailDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} headingId={railHeading} returnFocus={returnFocus}>
          <SourceRail paper={active ? byRef.get(active.ref) ?? null : null} outcome={active?.outcome} lang={lang}
            onClose={() => setDrawerOpen(false)} headingId={railHeading} visible={drawerOpen} type={type} onSelect={select}
            onReference={toReference} support={support} claim={active?.claim} />
        </RailDrawer>
      )}
    </div>
    </SameModelReadings.Provider>
    </PrintMode.Provider>
  );
}

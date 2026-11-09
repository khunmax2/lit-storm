// The report's contents as six chapters (DeepLit's layout): only the chapter being read opens its sections. Pure.
import { RC, type Pair } from "./i18n-report";
import type { TopSectionId } from "./review-type";

/** "try_this" is the block a report with no study shows after the answer. */
export type TocSection = TopSectionId | "try_this";

export interface TocEntry { section: TocSection; id: string; label: string }
export interface TocItem { id: string; label: string }
export interface Chapter {
  label: Pair;
  /** where the chapter's own link goes: its named section, else its first section on the page */
  head: string;
  /** the sections listed under the chapter; a named section is the chapter's own link instead */
  items: TocItem[];
  /** every anchor the chapter holds: it opens while the reader is at any of them */
  ids: string[];
}

const N = RC.nav;
const DEFS: { label: Pair; own?: TocSection; members: TocSection[] }[] = [
  { label: N.answer, own: "bottom_line", members: ["try_this", "key_findings", "sof"] },
  { label: N.chapterStudies, members: ["selection", "characteristics"] },
  { label: N.results, own: "results", members: ["landscape"] },
  { label: N.chapterTrust, members: ["rob", "consistency", "limitations"] },
  { label: N.discussion, own: "discussion", members: ["gaps"] },
  { label: N.chapterSources, members: ["methods", "appendix", "downloads", "references"] },
];

/** The chapters that have a section on the page, in the order the reader meets them (the audience reorders the page). */
export function chapters(entries: TocEntry[]): Chapter[] {
  const at = new Map(entries.map((e, i) => [e.section, i]));
  const made: { first: number; chapter: Chapter }[] = [];
  for (const d of DEFS) {
    const own = d.own ? entries[at.get(d.own) ?? -1] : undefined;
    const members = d.members.flatMap((m) => (at.has(m) ? [entries[at.get(m)!]] : []));
    const inPage = [...(own ? [own] : []), ...members];
    if (!inPage.length) continue;
    made.push({
      first: Math.min(...inPage.map((e) => at.get(e.section)!)),
      chapter: {
        label: d.label,
        head: inPage[0].id,
        items: members.map(({ id, label }) => ({ id, label })),
        ids: inPage.map((e) => e.id),
      },
    });
  }
  return made.sort((a, b) => a.first - b.first).map((m) => m.chapter);
}

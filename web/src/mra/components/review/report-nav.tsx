"use client";

import { createContext, Fragment, useContext, useEffect, useState, type ReactNode } from "react";
import type { Chapter } from "@mra/lib/report-toc";
import type { Lang } from "@mra/lib/i18n";
import { ThaiText } from "../ui/thai-text";
import { byId } from "@mra/lib/host";
import { L } from "./text";

/** Section headings the nav links to: the jump clears the site header (--header-h) and the sticky nav. */
export const SECTION_H2 = "scroll-mt-[calc(var(--header-h)+env(safe-area-inset-top,0px)+3.5rem)] text-[21px] leading-[1.35] font-bold";
/** A block inside a group section (Plan 20): one level down, same jump offset. */
export const SECTION_H3 = "scroll-mt-[calc(var(--header-h)+env(safe-area-inset-top,0px)+3.5rem)] font-display text-[15px] leading-[1.45] font-semibold";

const Nested = createContext(false);

/** Wraps the blocks of a group section (results, landscape …): their headings become H3 under the group's H2. */
export function Subsections({ children }: { children: ReactNode }) {
  return <Nested.Provider value>{children}</Nested.Provider>;
}

/** True inside a group section: a block's own sub-headings go one level down too. */
export function useNested(): boolean {
  return useContext(Nested);
}

/** A block's heading: H2 on its own, H3 inside a group section. Thai text wraps only between words (ThaiText). */
export function SectionHeading({ id, children, className = "" }: { id: string; children: ReactNode; className?: string }) {
  const text = typeof children === "string" ? <ThaiText>{children}</ThaiText> : children;
  return useContext(Nested)
    ? <h3 id={id} className={`${SECTION_H3} ${className}`}>{text}</h3>
    : <h2 id={id} className={`${SECTION_H2} ${className}`}>{text}</h2>;
}

/**
 * The section being read: the last one whose heading has passed the top quarter of the window, or the last on the page
 * once the page has run out (short sections at the end never reach that line).
 */
function useCurrentSection(ids: string[]): string | null {
  const [current, setCurrent] = useState<string | null>(null);
  const key = ids.join("|");
  useEffect(() => {
    const list = key.split("|").filter(Boolean);
    let frame = 0;
    const measure = () => {
      frame = 0;
      const line = window.innerHeight * 0.25;
      const placed = list.map((id) => ({ id, top: byId(id)?.getBoundingClientRect().top ?? Infinity }))
        .filter((s) => s.top !== Infinity).sort((a, b) => a.top - b.top);
      if (!placed.length) return;
      const last = placed[placed.length - 1];
      // two sections side by side start at the same height: the first of them is the one being read
      const passed = placed.filter((s) => s.top <= line).pop() ?? placed[0];
      const first = placed.find((s) => Math.abs(s.top - passed.top) < 2) ?? passed;
      const end = last.top < window.innerHeight * 0.9
        && document.documentElement.scrollHeight - window.scrollY - window.innerHeight < 8;
      setCurrent(end ? last.id : first.id);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(measure); };
    measure();
    // capture: the page may scroll inside an element of the app around the report
    window.addEventListener("scroll", onScroll, { capture: true, passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [key]);
  return current;
}

/**
 * The report's contents: six chapters, of which only the one being read opens its sections. From `lg` a list beside the
 * report, as wide as its longest label; narrower, a row of chapters under the site header. Both stay in view.
 */
export function ReportChapters({ chapters, label, lang }: { chapters: Chapter[]; label: string; lang: Lang }) {
  const current = useCurrentSection(chapters.flatMap((c) => c.ids));
  if (!chapters.length) return null;
  return (
    <nav aria-label={label} className="mra-toc lg:col-start-2 lg:row-start-2 print:hidden">
      <span className="mra-toc-h">{label}</span>
      {chapters.map((c) => {
        const open = current != null && c.ids.includes(current);
        const listed = c.items.some((i) => i.id === c.head);
        return (
          <Fragment key={c.head}>
            <a href={`#${c.head}`} className="mra-tocitem" data-open={open}
              aria-current={!listed && current === c.head ? "location" : undefined}>{L(lang, c.label)}</a>
            {c.items.map((i) => (
              <a key={i.id} href={`#${i.id}`} className="mra-tocsub" data-show={open}
                aria-current={current === i.id ? "location" : undefined}>{i.label}</a>
            ))}
          </Fragment>
        );
      })}
    </nav>
  );
}

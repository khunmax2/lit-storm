"use client";

import { useMemo } from "react";
import type { ConceptTree } from "@mra/lib/concept-map";
import type { Lang } from "@mra/lib/i18n";
import { RC } from "@mra/lib/i18n-report";
import { ConceptMapFigure } from "../charts/figures";
import { readTokens } from "../charts/tokens";
import { useTheme } from "../theme-toggle";
import { SectionHeading } from "./report-nav";
import { L } from "./text";

/**
 * Concept map section: a tree of the question, its outcomes and the papers that report them. It opens as the outline
 * (the card is half a page wide), with a toggle to the chart. Offline-safe.
 */
export function ConceptMapSection({ tree, lang, onSelect }: { tree: ConceptTree; lang: Lang; onSelect: (ref: string) => void }) {
  const theme = useTheme();
  const tokens = useMemo(() => (theme ? readTokens() : null), [theme]);
  return (
    <section aria-labelledby="h-map" className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
      <SectionHeading id="h-map">{L(lang, RC.network.conceptMap)}</SectionHeading>
      {tokens && <ConceptMapFigure tree={tree} tokens={tokens} lang={lang} onSelect={onSelect} wide={false} />}
    </section>
  );
}

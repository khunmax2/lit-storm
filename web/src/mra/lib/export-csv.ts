// The review as CSV, in the browser: the same columns and rules as MRA's export (backend/app/services/report.py
// render_csv), since DeepLit keeps the review and does not ask MRA again. One row per paper × outcome, from the English cards.
import { NON_QUANTITATIVE_DESIGNS } from "./charts-data";
import type { ReviewResult } from "./types";

const FIELDS = ["ref", "title", "year", "journal", "doi", "pmid", "design_category", "study_design", "sample_size",
  "outcome", "direction", "effect_measure", "effect_value", "ci_lower", "ci_upper", "p_value", "evidence_quote", "error",
  "population", "intervention_or_exposure", "comparator", "risk_of_bias", "overall_direction", "key_findings", "limitations",
  "comparison", "matches_question"];

type Row = Record<string, unknown>;

/** Text a spreadsheet would run as a formula (titles and quotes come from third-party metadata) gets a leading apostrophe. */
function cell(value: unknown): string {
  if (value == null) return "";
  const text = String(value);
  const safe = typeof value === "string" && /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function reviewCsv(result: ReviewResult | null | undefined): string {
  const scoping = result?.review_type === "scoping";
  const lines = [FIELDS.join(",")];
  const push = (row: Row) => lines.push(FIELDS.map((k) => cell(row[k])).join(","));
  for (const p of result?.papers ?? []) {
    const card = (p.card_en ?? p.card) as unknown as Row | null | undefined;
    const base: Row = { ref: p.ref, title: p.title, year: p.year, journal: p.journal, doi: p.doi, pmid: p.pmid, error: p.error };
    if (!card) {
      push(base);
      continue;
    }
    const joined = (k: string) => ((card[k] as unknown[] | undefined) ?? []).map(String).join(" | ");
    for (const k of ["design_category", "study_design", "sample_size", "population", "intervention_or_exposure", "comparator",
      "risk_of_bias", "overall_direction"]) base[k] = card[k];
    base.key_findings = joined("key_findings");
    base.limitations = joined("limitations");
    const outcomes = (card.outcomes as Row[] | undefined) ?? [];
    for (const o of outcomes.length ? outcomes : [{} as Row]) {
      const row: Row = { ...base };
      for (const k of ["outcome", "direction", "effect_measure", "effect_value", "ci_lower", "ci_upper", "p_value", "evidence_quote", "comparison"]) row[k] = o[k];
      if (Object.keys(o).length) row.matches_question = o.matches_question === false ? "false" : "true";
      if (scoping) Object.assign(row, { direction: null, overall_direction: null, risk_of_bias: null });
      else if (NON_QUANTITATIVE_DESIGNS.includes(String(card.design_category))) Object.assign(row, { direction: null, overall_direction: null });
      push(row);
    }
  }
  return `﻿${lines.join("\n")}\n`;
}

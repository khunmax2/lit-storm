// What a Run made of its topic before researching it (server: litstorm.interpret):
// on the Run's card, and as the report's method.
import { Compass } from "lucide-react";

import { useT } from "@/i18n";

export type Reading = {
  question?: string;
  scope?: string[];
  assumptions?: string[];
  keywords?: Partial<Record<"en" | "th", string[]>>;
  exclude?: string[];
  // The keyword languages the research was given: English, and Thai for Thai research.
  searched?: ("en" | "th")[];
  failed?: string;
};

/** The reading as labelled rows after its question; only the search terms research was given. */
function useRows(reading: Reading) {
  const { t } = useT();
  const rows: [string, string][] = [];
  if (reading.scope?.length) rows.push([t("reading.scope"), reading.scope.join("; ")]);
  if (reading.assumptions?.length) rows.push([t("reading.assumptions"), reading.assumptions.join("; ")]);
  const terms = (reading.searched ?? ["en"])
    .filter((lang) => reading.keywords?.[lang]?.length)
    .map((lang) => `${t(lang === "th" ? "lang.th" : "lang.en")}: ${reading.keywords![lang]!.join(", ")}`);
  if (terms.length) rows.push([t("reading.keywords"), terms.join(" · ")]);
  if (reading.exclude?.length) rows.push([t("reading.exclude"), reading.exclude.join("; ")]);
  return rows;
}

/** On the Run's card: the question it researches, opening to the rest. */
export function RunReading({ reading }: { reading?: Reading }) {
  const { t } = useT();
  const rows = useRows(reading ?? {});
  if (!reading?.question) return null;
  return (
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer select-none">
        {t("reading.readAs")} <span className="text-foreground/80">{reading.question}</span>
      </summary>
      {rows.length > 0 && (
        <dl className="mt-1.5 grid gap-1 pl-3">
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd className="text-foreground/80">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </details>
  );
}

/** After the report's text: how the topic was read, as the exports show it. */
export function ReportMethod({ reading }: { reading?: Reading }) {
  const { t } = useT();
  const rows = useRows(reading ?? {});
  if (!reading?.question) return null;
  return (
    <section id="method" className="mt-14 scroll-mt-24 rounded-xl border bg-muted/30 p-5">
      <h2 className="mb-4 flex items-center gap-2 font-display text-xl tracking-tight">
        <Compass className="size-4 text-brand" />
        {t("report.method")}
      </h2>
      <dl className="grid gap-3 text-sm">
        {[[t("reading.readAs"), reading.question] as [string, string], ...rows].map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="mt-0.5">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-muted-foreground">{t("report.methodNote")}</p>
    </section>
  );
}

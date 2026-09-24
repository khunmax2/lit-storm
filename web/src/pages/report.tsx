// Reading a Report: contents on the left, the text in the middle, and a
// Source panel that opens beside the text when a citation is clicked — the
// page never changes (docs/web-app-design.md, ขอบเขต Source Explorer).
import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import MarkdownIt from "markdown-it";
import { useMemo, useState, type MouseEvent } from "react";

import { api, call } from "../api/client";
import { Button, ErrorText, Spinner } from "../components/ui";
import { useT } from "../i18n";

type Source = { id: number; url: string; title: string; description?: string; evidence: string[] };
type Section = { id: string; heading: string; body: string; children: Section[] };
type Report = { title: string; language: string; lead: string; sections: Section[]; sources: Source[] };

// Model output is untrusted: raw HTML stays text, and markdown-it refuses
// javascript: links by itself.
const md = new MarkdownIt({ html: false, linkify: false });

function render(text: string) {
  return md
    .render(text || "")
    .replace(/\[(\d+)\]/g, (_, n) => `<button type="button" class="cite" data-cite="${n}">[${n}]</button>`);
}

function Contents({ sections, depth = 0 }: { sections: Section[]; depth?: number }) {
  if (!sections.length) return null;
  return (
    <ol className={depth ? "ml-3 mt-1 border-l border-line pl-3" : ""}>
      {sections.map((s) => (
        <li key={s.id} className="my-1">
          <a href={`#${s.id}`} className="text-muted hover:text-ink">
            {s.heading}
          </a>
          <Contents sections={s.children} depth={depth + 1} />
        </li>
      ))}
    </ol>
  );
}

function Body({ sections, level = 2 }: { sections: Section[]; level?: number }) {
  return (
    <>
      {sections.map((s) => {
        const size = level === 2 ? "text-xl mt-10" : level === 3 ? "text-lg mt-7" : "text-base mt-5";
        return (
          <section key={s.id}>
            <h2 id={s.id} className={`${size} mb-3 scroll-mt-20 font-semibold`}>
              {s.heading}
            </h2>
            <div dangerouslySetInnerHTML={{ __html: render(s.body) }} />
            <Body sections={s.children} level={level + 1} />
          </section>
        );
      })}
    </>
  );
}

function SourcePanel({ source, onClose }: { source: Source; onClose: () => void }) {
  const { t } = useT();
  const safe = /^https?:\/\//.test(source.url);
  return (
    <aside className="fixed inset-x-0 bottom-0 z-20 max-h-[70vh] overflow-y-auto border-t border-line bg-surface p-5 shadow-lg lg:inset-y-0 lg:left-auto lg:right-0 lg:max-h-none lg:w-[26rem] lg:border-l lg:border-t-0">
      <div className="mb-3 flex items-start justify-between gap-3">
        <span className="rounded bg-sunk px-2 py-0.5 text-xs text-muted">[{source.id}]</span>
        <button className="text-sm text-muted hover:text-ink" onClick={onClose}>
          {t("close")} ✕
        </button>
      </div>
      <h3 className="font-semibold leading-snug">{source.title}</h3>
      <p className="mt-1 break-all text-xs text-muted">{source.url}</p>
      {safe && (
        <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block">
          <Button variant="quiet">{t("report.openSource")} ↗</Button>
        </a>
      )}
      <h4 className="mt-6 text-sm font-semibold">{t("report.evidence")}</h4>
      {source.evidence.length ? (
        <>
          <p className="mb-2 text-xs text-muted">{t("report.excerpt")}</p>
          {source.evidence.map((e, i) => (
            <blockquote key={i} className="my-2 border-l-2 border-line bg-sunk px-3 py-2 text-sm leading-relaxed">
              {e}
            </blockquote>
          ))}
        </>
      ) : (
        <p className="text-sm text-muted">{t("report.noEvidence")}</p>
      )}
    </aside>
  );
}

function ExportMenu({ runId }: { runId: string }) {
  const { t } = useT();
  const [evidence, setEvidence] = useState(false);
  const href = (format: string) => `/api/runs/${runId}/export?format=${format}&evidence=${evidence}`;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-muted">{t("report.export")}:</span>
      {["pdf", "html", "md"].map((f) => (
        <a key={f} href={href(f)} className="rounded-md border border-line bg-surface px-2.5 py-1 hover:bg-sunk">
          {f.toUpperCase()}
        </a>
      ))}
      <label className="ml-1 flex items-center gap-1.5 text-muted">
        <input type="checkbox" checked={evidence} onChange={(e) => setEvidence(e.target.checked)} />
        {t("report.withEvidence")}
      </label>
    </div>
  );
}

export function ReportPage() {
  const { t } = useT();
  const { runId } = useParams({ from: "/app/runs/$runId" });
  const report = useQuery({
    queryKey: ["report", runId],
    queryFn: () => call(api.GET("/api/runs/{run_id}/report", { params: { path: { run_id: runId } } })) as Promise<Report>,
  });
  const [open, setOpen] = useState<number | null>(null);
  const byId = useMemo(() => new Map((report.data?.sources ?? []).map((s) => [s.id, s])), [report.data]);

  const onClick = (e: MouseEvent) => {
    const cite = (e.target as HTMLElement).closest("[data-cite]") as HTMLElement | null;
    if (cite) setOpen(Number(cite.dataset.cite));
  };

  if (report.isLoading) return <Spinner />;
  if (!report.data) return <ErrorText error={report.error} />;
  const r = report.data;
  const source = open != null ? byId.get(open) : undefined;

  return (
    <div className="lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-10">
      <nav className="hidden text-sm lg:block">
        <div className="sticky top-20">
          <h2 className="mb-2 font-semibold">{t("report.contents")}</h2>
          <Contents sections={r.sections} />
        </div>
      </nav>
      <article lang={r.language} className="min-w-0 max-w-3xl" onClick={onClick}>
        <button onClick={() => history.back()} className="mb-4 text-sm text-muted hover:text-ink">
          ← {t("back")}
        </button>
        <h1 className="mb-4 text-3xl font-semibold leading-tight tracking-tight">{r.title}</h1>
        <div className="mb-8">
          <ExportMenu runId={runId} />
        </div>
        <div className="prose-report">
          <div dangerouslySetInnerHTML={{ __html: render(r.lead) }} />
          <Body sections={r.sections} />
        </div>
        <section className="mt-12 border-t border-line pt-6">
          <h2 className="mb-3 text-xl font-semibold">{t("report.sources")}</h2>
          <ol className="flex flex-col gap-2 text-sm">
            {r.sources.map((s) => (
              <li key={s.id}>
                <button className="text-left hover:text-accent" onClick={() => setOpen(s.id)}>
                  <span className="text-muted">[{s.id}]</span> {s.title}
                </button>
              </li>
            ))}
          </ol>
        </section>
      </article>
      {source && <SourcePanel source={source} onClose={() => setOpen(null)} />}
    </div>
  );
}

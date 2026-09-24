// Reading a Report, in the style of Perplexity and NotebookLM: the sources
// as a strip under the title, the article in a comfortable column, contents on
// the right, and a panel that opens beside the text when a citation is clicked
// — the page never changes (docs/web-app-design.md, ขอบเขต Source Explorer).
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import MarkdownIt from "markdown-it";
import { ChevronLeft, Download, ExternalLink, FileCode2, FileText, FileType2, Quote } from "lucide-react";
import { useMemo, useState, type MouseEvent } from "react";

import { api, call } from "@/api/client";
import { ErrorText, LoadingRows, Toolbar, domainOf } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useT } from "@/i18n";

type Source = { id: number; url: string; title: string; description?: string; evidence: string[] };
type Section = { id: string; heading: string; body: string; children: Section[] };
type Report = { title: string; language: string; lead: string; sections: Section[]; sources: Source[] };

// Model output is untrusted: raw HTML stays text, and markdown-it refuses
// javascript: links by itself.
const md = new MarkdownIt({ html: false, linkify: false });

function render(text: string) {
  return md
    .render(text || "")
    .replace(/\[(\d+)\]/g, (_, n) => `<button type="button" class="cite" data-cite="${n}">${n}</button>`);
}

function readable(url: string) {
  // Thai addresses arrive percent-encoded; show them as a reader would type them.
  try {
    return decodeURI(url);
  } catch {
    return url;
  }
}

function Favicon({ url, className = "size-4" }: { url: string; className?: string }) {
  // A letter, not a fetched icon: the page stays free of third-party requests.
  const d = domainOf(url);
  return (
    <span
      className={`${className} inline-flex shrink-0 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold uppercase text-muted-foreground`}
    >
      {d.charAt(0)}
    </span>
  );
}

function Contents({ sections, depth = 0 }: { sections: Section[]; depth?: number }) {
  if (!sections.length) return null;
  return (
    <ul className={depth ? "mt-1 ml-3 space-y-1 border-l pl-3" : "space-y-1"}>
      {sections.map((s) => (
        <li key={s.id}>
          <a href={`#${s.id}`} className="line-clamp-2 text-muted-foreground transition-colors hover:text-foreground">
            {s.heading}
          </a>
          <Contents sections={s.children} depth={depth + 1} />
        </li>
      ))}
    </ul>
  );
}

function Body({ sections, level = 2 }: { sections: Section[]; level?: number }) {
  return (
    <>
      {sections.map((s) => {
        const size = level === 2 ? "text-xl mt-12" : level === 3 ? "text-lg mt-8" : "text-base mt-6";
        return (
          <section key={s.id}>
            <h2 id={s.id} className={`${size} mb-3 scroll-mt-20 font-semibold tracking-tight`}>
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

function ExportMenu({ runId }: { runId: string }) {
  const { t } = useT();
  const [evidence, setEvidence] = useState(false);
  const href = (format: string) => `/api/runs/${runId}/export?format=${format}&evidence=${evidence}`;
  const item = (format: string, label: string, Icon: typeof FileText) => (
    <DropdownMenuItem asChild>
      <a href={href(format)}>
        <Icon />
        {label}
      </a>
    </DropdownMenuItem>
  );
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Download />
          {t("report.download")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{t("report.export")}</DropdownMenuLabel>
        {item("pdf", "PDF", FileText)}
        {item("html", "HTML", FileCode2)}
        {item("md", "Markdown", FileType2)}
        <DropdownMenuSeparator />
        <DropdownMenuCheckboxItem
          checked={evidence}
          onCheckedChange={(v) => setEvidence(!!v)}
          onSelect={(e) => e.preventDefault()}
        >
          {t("report.withEvidence")}
        </DropdownMenuCheckboxItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SourceSheet({ source, onClose }: { source?: Source; onClose: () => void }) {
  const { t } = useT();
  const safe = source && /^https?:\/\//.test(source.url);
  return (
    <Sheet open={!!source} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        {source && (
          <>
            <SheetHeader className="border-b">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary" className="bg-brand-soft text-brand">
                  {source.id}
                </Badge>
                <Favicon url={source.url} />
                <span className="truncate">{domainOf(source.url)}</span>
              </div>
              <SheetTitle className="text-base leading-snug">{source.title}</SheetTitle>
              <SheetDescription className="break-all text-xs">{readable(source.url)}</SheetDescription>
              {safe && (
                <Button variant="outline" size="sm" className="mt-2 w-fit" asChild>
                  <a href={source.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink />
                    {t("report.openSource")}
                  </a>
                </Button>
              )}
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-3 p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Quote className="size-4 text-muted-foreground" />
                  {t("report.evidence")}
                </div>
                {source.evidence.length ? (
                  <>
                    <p className="text-xs text-muted-foreground">{t("report.excerpt")}</p>
                    {source.evidence.map((e, i) => (
                      <blockquote
                        key={i}
                        className="rounded-lg border-l-2 border-brand bg-muted/50 px-3 py-2 text-sm leading-relaxed"
                      >
                        {e}
                      </blockquote>
                    ))}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">{t("report.noEvidence")}</p>
                )}
              </div>
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function ReportPage() {
  const { t } = useT();
  const { runId } = useParams({ from: "/app/runs/$runId" });
  const report = useQuery({
    queryKey: ["report", runId],
    queryFn: () => call(api.GET("/api/runs/{run_id}/report", { params: { path: { run_id: runId } } })) as Promise<Report>,
  });
  const run = useQuery({
    queryKey: ["run-summary", runId],
    queryFn: () => call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId } } })),
  });
  const [open, setOpen] = useState<number | null>(null);
  const byId = useMemo(() => new Map((report.data?.sources ?? []).map((s) => [s.id, s])), [report.data]);

  const onClick = (e: MouseEvent) => {
    const cite = (e.target as HTMLElement).closest("[data-cite]") as HTMLElement | null;
    if (cite) setOpen(Number(cite.dataset.cite));
  };

  if (report.isLoading)
    return (
      <div className="mx-auto w-full max-w-3xl p-8">
        <LoadingRows rows={6} />
      </div>
    );
  if (!report.data)
    return (
      <div className="p-8">
        <ErrorText error={report.error} />
      </div>
    );
  const r = report.data;
  const sessionId = run.data?.session_id;

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-8">
      <Toolbar>
        {sessionId && (
          <Button variant="ghost" size="sm" asChild>
            <Link to="/sessions/$sessionId" params={{ sessionId }}>
              <ChevronLeft />
              {t("report.back")}
            </Link>
          </Button>
        )}
        <span className="min-w-0 truncate text-sm font-medium">{r.title}</span>
        <div className="ml-auto">
          <ExportMenu runId={runId} />
        </div>
      </Toolbar>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_15rem]">
        <article lang={r.language} className="min-w-0 max-w-3xl" onClick={onClick}>
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-balance md:text-4xl">{r.title}</h1>

          {/* The sources up front, as Perplexity shows them. */}
          <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {r.sources.slice(0, 3).map((s) => (
              <button
                key={s.id}
                onClick={() => setOpen(s.id)}
                className="flex flex-col gap-2 rounded-xl border bg-card p-3 text-left transition-colors hover:bg-muted/50"
              >
                <span className="line-clamp-2 text-xs font-medium leading-snug">{s.title}</span>
                <span className="mt-auto flex items-center gap-1.5 text-[0.7rem] text-muted-foreground">
                  <Favicon url={s.url} className="size-3.5" />
                  <span className="truncate">{domainOf(s.url)}</span>
                  <span className="ml-auto">{s.id}</span>
                </span>
              </button>
            ))}
            {r.sources.length > 3 && (
              <a
                href="#sources"
                className="flex flex-col justify-between gap-2 rounded-xl border bg-card p-3 text-xs transition-colors hover:bg-muted/50"
              >
                <span className="flex -space-x-1">
                  {r.sources.slice(3, 7).map((s) => (
                    <Favicon key={s.id} url={s.url} className="size-4 ring-2 ring-card" />
                  ))}
                </span>
                <span className="text-muted-foreground">{t("report.sourcesCount", { n: r.sources.length })}</span>
              </a>
            )}
          </div>

          <div className="prose-report mt-8">
            <div dangerouslySetInnerHTML={{ __html: render(r.lead) }} />
            <Body sections={r.sections} />
          </div>

          <Separator className="my-12" />
          <section id="sources" className="scroll-mt-20">
            <h2 className="mb-4 text-lg font-semibold">{t("report.allSources")}</h2>
            <div className="grid gap-2">
              {r.sources.map((s) => (
                <Card key={s.id} className="py-0">
                  <CardContent className="p-0">
                    <button
                      onClick={() => setOpen(s.id)}
                      className="flex w-full items-start gap-3 p-3 text-left hover:bg-muted/40"
                    >
                      <Badge variant="secondary" className="mt-0.5 shrink-0 bg-brand-soft text-brand">
                        {s.id}
                      </Badge>
                      <span className="min-w-0">
                        <span className="line-clamp-1 text-sm font-medium">{s.title}</span>
                        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Favicon url={s.url} className="size-3.5" />
                          <span className="truncate">{domainOf(s.url)}</span>
                        </span>
                      </span>
                    </button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        </article>

        <aside className="hidden lg:block">
          <nav className="sticky top-20 text-sm">
            <p className="mb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t("report.onThisPage")}
            </p>
            <Contents sections={r.sections} />
          </nav>
        </aside>
      </div>

      <SourceSheet source={open != null ? byId.get(open) : undefined} onClose={() => setOpen(null)} />
    </div>
  );
}

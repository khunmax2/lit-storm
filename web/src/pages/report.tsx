// Reading a Report, in the style of Perplexity and NotebookLM: the sources
// as a strip under the title, the article in a comfortable column, contents on
// the right, and a panel that opens beside the text when a citation is clicked
// — the page never changes (docs/web-app-design.md, ขอบเขต Source Explorer).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import MarkdownIt from "markdown-it";
import {
  ArrowUp,
  BookOpen,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  Eye,
  EyeOff,
  ExternalLink,
  FileCode2,
  FileText,
  FileType2,
  Library,
  Loader2,
  PanelsTopLeft,
  Quote,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

import { api, BASE, call } from "@/api/client";
import { ErrorText, Favicon, LoadingRows, Toolbar, domainOf } from "@/components/common";
import { Segmented } from "@/components/segmented";
import { Button } from "@/components/ui/button";
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
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

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

/** Minutes to read: Thai has no spaces between words, so it is counted in
 *  letters (about 900 a minute); other languages in words (about 230). */
function readingMinutes(r: Report) {
  const all = (s: Section[]): string => s.map((x) => `${x.heading} ${x.body} ${all(x.children)}`).join(" ");
  const text = `${r.lead} ${all(r.sections)}`.replace(/\[\d+\]/g, "");
  const n = r.language === "th" ? text.replace(/\s/g, "").length / 900 : text.split(/\s+/).length / 230;
  return Math.max(1, Math.round(n));
}


function Num({ id, className }: { id: number; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-brand-soft px-1.5 text-[0.7rem] font-medium tabular-nums text-brand",
        className,
      )}
    >
      {id}
    </span>
  );
}

/** "1", "1.2": where a section sits, shown beside its heading and in the contents. */
function numbered(sections: Section[], prefix = ""): (Section & { n: string; children: ReturnType<typeof numbered> })[] {
  return sections.map((s, i) => {
    const n = prefix ? `${prefix}.${i + 1}` : `${i + 1}`;
    return { ...s, n, children: numbered(s.children, n) };
  });
}
type Numbered = ReturnType<typeof numbered>[number];

function Contents({ sections, active, depth = 0 }: { sections: Numbered[]; active: string; depth?: number }) {
  if (!sections.length) return null;
  return (
    <ul className={depth ? "mt-1 ml-3 space-y-0.5" : "space-y-0.5"}>
      {sections.map((s) => {
        const on = s.id === active;
        return (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              aria-current={on ? "location" : undefined}
              className={cn(
                "relative flex gap-2 rounded-md py-1 pr-2 pl-3 leading-snug transition-colors duration-200",
                "before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:rounded-full before:transition-colors before:duration-200",
                on
                  ? "font-medium text-foreground before:bg-brand"
                  : "text-muted-foreground before:bg-transparent hover:text-foreground",
              )}
            >
              <span className={cn("shrink-0 tabular-nums", on ? "text-brand" : "text-muted-foreground/70")}>{s.n}</span>
              <span className="line-clamp-2">{s.heading}</span>
            </a>
            <Contents sections={s.children} active={active} depth={depth + 1} />
          </li>
        );
      })}
    </ul>
  );
}

function Body({ sections, level = 2 }: { sections: Numbered[]; level?: number }) {
  return (
    <>
      {sections.map((s) => {
        const top = level === 2;
        const Tag = top ? "h2" : level === 3 ? "h3" : "h4";
        return (
          <section key={s.id}>
            <Tag
              id={s.id}
              data-heading
              className={cn(
                "flex scroll-mt-24 items-baseline gap-3 tracking-tight text-balance",
                top
                  ? "mt-14 mb-4 border-t pt-8 font-display text-[1.75rem] leading-snug md:text-3xl"
                  : level === 3
                    ? "mt-9 mb-3 text-lg font-semibold"
                    : "mt-7 mb-2 text-base font-semibold",
              )}
            >
              <span
                className={cn(
                  "shrink-0 font-sans tabular-nums",
                  top ? "text-sm font-medium text-brand" : "text-sm font-normal text-muted-foreground",
                )}
              >
                {top ? s.n.padStart(2, "0") : s.n}
              </span>
              <span>{s.heading}</span>
            </Tag>
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
  const [live, setLive] = useState(false);
  const href = (format: string) =>
    `${BASE}/api/runs/${runId}/export?format=${format}&evidence=${evidence}&charts=${live ? "full" : "static"}`;
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
        <Button variant="outline" size="sm" aria-label={t("report.download")}>
          <Download />
          {/* On a phone the toolbar also holds the view switch: the icon is enough. */}
          <span className="hidden sm:inline">{t("report.download")}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{t("report.export")}</DropdownMenuLabel>
        {item("pdf", "PDF", FileText)}
        {item("html", "HTML", FileCode2)}
        {item("md", "Markdown", FileType2)}
        {item("interactive", t("report.exportInteractive"), PanelsTopLeft)}
        <DropdownMenuSeparator />
        <DropdownMenuCheckboxItem
          checked={evidence}
          onCheckedChange={(v) => setEvidence(!!v)}
          onSelect={(e) => e.preventDefault()}
        >
          {t("report.withEvidence")}
        </DropdownMenuCheckboxItem>
        <DropdownMenuCheckboxItem checked={live} onCheckedChange={(v) => setLive(!!v)} onSelect={(e) => e.preventDefault()}>
          {t("report.fullCharts")}
        </DropdownMenuCheckboxItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type VisualBlock = { id: string; type: string; title: string; anchor: string; hidden: boolean; sources: number[] };
type Visuals = {
  ready: boolean;
  blocks: VisualBlock[];
  dropped: number;
  model: string | null;
  created_at: string | null;
  from_report_text: boolean;
  outdated: boolean;
};

/** The report with its figures (litstorm.render.interactive), shown as the
 *  server draws it, in a frame of its own: the page runs a script, so it is
 *  sandboxed — no reach into this app, its cookies or its API. It scrolls
 *  inside the frame, keeping its own contents and progress. */
function VisualView({ runId }: { runId: string }) {
  const { t } = useT();
  const { resolvedTheme } = useTheme();
  const client = useQueryClient();
  const key = ["visuals", runId];
  const visuals = useQuery({
    queryKey: key,
    queryFn: () => call(api.GET("/api/runs/{run_id}/visuals", { params: { path: { run_id: runId } } })) as Promise<Visuals>,
  });
  // Drawn once; drawn again on the owner's word, as today's code draws (the
  // figures kept so far stay until the new ones are in).
  const make = useMutation({
    mutationFn: (again: boolean) =>
      call(
        api.POST("/api/runs/{run_id}/visuals", { params: { path: { run_id: runId }, query: { again } } }),
      ) as Promise<Visuals>,
    onSuccess: (v) => client.setQueryData(key, v),
  });
  const hide = useMutation({
    mutationFn: (hidden: string[]) =>
      call(
        api.PATCH("/api/runs/{run_id}/visuals", { params: { path: { run_id: runId } }, body: { hidden } }),
      ) as Promise<Visuals>,
    onSuccess: (v) => client.setQueryData(key, v),
  });
  const v = visuals.data;
  const hidden = (v?.blocks ?? []).filter((b) => b.hidden).map((b) => b.id);
  // The frame reloads when what it shows changes.
  const version = `${v?.ready ? v.created_at : "none"}-${hidden.join(",")}`;
  const theme = resolvedTheme === "dark" ? "dark" : "light";
  const src = `${BASE}/api/runs/${runId}/interactive?theme=${theme}&v=${encodeURIComponent(version)}`;
  const [loading, setLoading] = useState(true);
  useEffect(() => setLoading(true), [src]);

  return (
    <div className="animate-in duration-300 fade-in-0 motion-reduce:animate-none">
      <div className="mb-4 rounded-2xl border bg-card p-4 md:p-5">
        {!v ? (
          <LoadingRows rows={2} />
        ) : !v.ready ? (
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 font-medium">
                <Sparkles className="size-4 text-brand" />
                {t("visuals.title")}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t("visuals.lead")}</p>
              {v.from_report_text && <p className="mt-1 text-xs text-muted-foreground">{t("visuals.leadReport")}</p>}
            </div>
            <Button onClick={() => make.mutate(false)} disabled={make.isPending} className="shrink-0">
              {make.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
              {make.isPending ? t("visuals.making") : t("visuals.make")}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <span className="flex items-center gap-2 font-medium">
                <Sparkles className="size-4 text-brand" />
                {t("visuals.made", { model: v.model ?? "AI", n: v.blocks.length })}
              </span>
              {v.dropped > 0 && <span className="text-xs text-muted-foreground">{t("visuals.dropped", { n: v.dropped })}</span>}
              <span className="ml-auto flex items-center gap-2">
                {v.outdated && !make.isPending && (
                  <span className="text-xs text-brand">{t("visuals.outdated")}</span>
                )}
                <Button
                  variant={v.outdated ? "default" : "outline"}
                  size="sm"
                  disabled={make.isPending}
                  onClick={() => make.mutate(true)}
                  title={t("visuals.againHint")}
                >
                  {make.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                  {make.isPending ? t("visuals.making") : t("visuals.again")}
                </Button>
              </span>
            </p>
            {v.blocks.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("visuals.none")}</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  {v.blocks.map((b) => {
                    const Icon = b.hidden ? EyeOff : Eye;
                    const next = b.hidden ? hidden.filter((h) => h !== b.id) : [...hidden, b.id];
                    return (
                      <button
                        key={b.id}
                        type="button"
                        disabled={hide.isPending}
                        onClick={() => hide.mutate(next)}
                        aria-pressed={!b.hidden}
                        title={b.hidden ? t("visuals.show") : t("visuals.hide")}
                        className={cn(
                          "inline-flex max-w-full items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-[background-color,color,opacity,transform] duration-200 hover:-translate-y-px active:scale-[0.97] motion-reduce:transform-none",
                          b.hidden ? "text-muted-foreground line-through opacity-60" : "bg-brand-soft/60 text-foreground",
                        )}
                      >
                        <Icon className="size-3.5 shrink-0" />
                        <span className="shrink-0 text-muted-foreground">{t(`visuals.type.${b.type}` as never)}</span>
                        <span className="truncate">{b.title}</span>
                      </button>
                    );
                  })}
                </div>
                <p className="text-xs text-muted-foreground">{t("visuals.hiddenNote")}</p>
              </>
            )}
          </div>
        )}
        {(make.error || hide.error) && (
          <div className="mt-3">
            <ErrorText error={make.error || hide.error} />
          </div>
        )}
      </div>
      <div className="relative overflow-hidden rounded-2xl border bg-background">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/70">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        )}
        <iframe
          key={src}
          title={t("report.view.visual")}
          src={src}
          // Its own origin: scripts run, links to Sources open, nothing else.
          sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
          referrerPolicy="no-referrer"
          onLoad={() => setLoading(false)}
          className="block h-[calc(100svh-9rem)] min-h-[32rem] w-full"
        />
      </div>
    </div>
  );
}

function SourceSheet({
  source,
  place,
  total,
  onClose,
  onStep,
}: {
  source?: Source;
  /** Its place in the list, from 1: numbers need not run without gaps. */
  place: number;
  total: number;
  onClose: () => void;
  onStep: (by: number) => void;
}) {
  const { t } = useT();
  const safe = source && /^https?:\/\//.test(source.url);
  return (
    <Sheet open={!!source} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        {source && (
          <>
            <SheetHeader className="border-b pr-12">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Num id={source.id} />
                <Favicon url={source.url} />
                <span className="truncate">{domainOf(source.url)}</span>
              </div>
              {/* A new source slides in, so stepping through them is seen. */}
              <div key={source.id} className="animate-in duration-300 fade-in-0 slide-in-from-right-2 motion-reduce:animate-none">
                <SheetTitle className="text-base leading-snug">{source.title}</SheetTitle>
                <SheetDescription className="mt-1 break-all text-xs">{readable(source.url)}</SheetDescription>
              </div>
              <div className="mt-2 flex items-center gap-2">
                {safe && (
                  <Button variant="outline" size="sm" className="w-fit" asChild>
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink />
                      {t("report.openSource")}
                    </a>
                  </Button>
                )}
                <span className="ml-auto flex items-center gap-1">
                  <span className="mr-1 text-xs text-muted-foreground tabular-nums">
                    {t("report.sourceOf", { n: place, total })}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t("report.prevSource")}
                    disabled={place <= 1}
                    onClick={() => onStep(-1)}
                  >
                    <ChevronLeft />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t("report.nextSource")}
                    disabled={place >= total}
                    onClick={() => onStep(1)}
                  >
                    <ChevronRight />
                  </Button>
                </span>
              </div>
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1">
              <div key={source.id} className="space-y-3 p-4 animate-in duration-300 fade-in-0 motion-reduce:animate-none">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Quote className="size-4 text-muted-foreground" />
                  {t("report.evidence")}
                  {source.evidence.length > 0 && (
                    <span className="text-xs font-normal text-muted-foreground">· {source.evidence.length}</span>
                  )}
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

/** A citation's source, shown beside it while the pointer rests on it. */
function CitePreview({ source, at }: { source: Source; at: DOMRect }) {
  const { t } = useT();
  const width = 300;
  const left = Math.max(12, Math.min(at.left + at.width / 2 - width / 2, window.innerWidth - width - 12));
  const below = at.bottom + 220 < window.innerHeight;
  return (
    <div
      role="tooltip"
      style={{ left, width, ...(below ? { top: at.bottom + 8 } : { bottom: window.innerHeight - at.top + 8 }) }}
      className={cn(
        "pointer-events-none fixed z-50 rounded-xl border bg-popover p-3 text-popover-foreground shadow-lg",
        "animate-in duration-150 fade-in-0 zoom-in-95 motion-reduce:animate-none",
        below ? "slide-in-from-top-1" : "slide-in-from-bottom-1",
      )}
    >
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Num id={source.id} className="h-4 min-w-4 px-1 text-[0.65rem]" />
        <Favicon url={source.url} className="size-3.5" />
        <span className="truncate">{domainOf(source.url)}</span>
      </div>
      <p className="mt-1.5 line-clamp-2 text-sm leading-snug font-medium">{source.title}</p>
      {source.evidence[0] && (
        <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-muted-foreground">“{source.evidence[0]}”</p>
      )}
      <p className="mt-2 text-[0.7rem] text-brand">{t("report.citeHint")}</p>
    </div>
  );
}

export function ReportPage() {
  const { t, lang } = useT();
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
  const [view, setView] = useState<"read" | "visual">("read");
  const [hover, setHover] = useState<{ id: number; at: DOMRect } | null>(null);
  const byId = useMemo(() => new Map((report.data?.sources ?? []).map((s) => [s.id, s])), [report.data]);
  const sections = useMemo(() => numbered(report.data?.sections ?? []), [report.data]);
  const article = useRef<HTMLElement>(null);
  const [active, setActive] = useState("");
  const [progress, setProgress] = useState(0);

  // Where the reader is: the last heading above the top of the view lights up
  // in the contents, and a line along the top shows how far through they are.
  useEffect(() => {
    const el = article.current;
    if (!el) return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      let current = "";
      for (const h of el.querySelectorAll<HTMLElement>("[data-heading]")) {
        if (h.getBoundingClientRect().top < 140) current = h.id;
        else break;
      }
      setActive(current);
      const box = el.getBoundingClientRect();
      const span = box.height - window.innerHeight;
      setProgress(span > 0 ? Math.min(1, Math.max(0, -box.top / span)) : 1);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame);
    };
  }, [report.data]);

  // The citation whose source is open stays lit.
  useEffect(() => {
    article.current?.querySelectorAll<HTMLElement>("[data-cite]").forEach((b) => {
      b.dataset.active = String(Number(b.dataset.cite) === open);
    });
  }, [open]);

  const citeOf = (e: MouseEvent) => (e.target as HTMLElement).closest("[data-cite]") as HTMLElement | null;
  const onClick = (e: MouseEvent) => {
    const cite = citeOf(e);
    if (cite) {
      setHover(null);
      setOpen(Number(cite.dataset.cite));
    }
  };
  const onOver = (e: MouseEvent) => {
    const cite = citeOf(e);
    const id = cite ? Number(cite.dataset.cite) : null;
    if (cite && id != null && byId.has(id)) {
      if (hover?.id !== id) setHover({ id, at: cite.getBoundingClientRect() });
    } else if (hover) setHover(null);
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
  const summary = run.data;
  const sessionId = summary?.session_id;
  const finished = summary?.finished_at
    ? new Date(summary.finished_at).toLocaleDateString(lang === "th" ? "th-TH" : "en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : null;
  const hovered = hover && byId.get(hover.id);

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-8">
      {/* How far through the report the reader is. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 top-0 z-40 h-0.5 origin-left bg-brand transition-transform duration-150 ease-out motion-reduce:transition-none"
        style={{ transform: `scaleX(${progress})` }}
      />
      <Toolbar>
        {sessionId && (
          <Button variant="ghost" size="sm" asChild>
            <Link to="/sessions/$sessionId" params={{ sessionId }} aria-label={t("report.back")}>
              <ChevronLeft />
              <span className="hidden sm:inline">{t("report.back")}</span>
            </Link>
          </Button>
        )}
        <span className="hidden min-w-0 truncate text-sm font-medium md:inline">{r.title}</span>
        <div className="ml-auto flex items-center gap-2">
          <Segmented
            label={t("report.view.visual")}
            value={view}
            onChange={setView}
            className="p-0.5 [&_button]:h-7 [&_button]:px-3 [&_button]:text-xs"
            options={[
              { value: "read", label: t("report.view.read") },
              { value: "visual", label: t("report.view.visual") },
            ]}
          />
          <ExportMenu runId={runId} />
        </div>
      </Toolbar>

      {view === "visual" ? (
        <VisualView runId={runId} />
      ) : (

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_15rem]">
        <article
          ref={article}
          lang={r.language}
          className="min-w-0 max-w-3xl animate-in duration-500 ease-out fade-in-0 slide-in-from-bottom-2 motion-reduce:animate-none"
          onClick={onClick}
          onMouseOver={onOver}
          onMouseLeave={() => setHover(null)}
        >
          <header>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
              {summary?.engine_label && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2.5 py-0.5 font-medium text-brand">
                  <Sparkles className="size-3" />
                  {summary.engine_label}
                </span>
              )}
              {finished && (
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="size-3.5" />
                  {finished}
                </span>
              )}
              <span className="inline-flex items-center gap-1.5">
                <Clock className="size-3.5" />
                {t("report.readMinutes", { n: readingMinutes(r) })}
              </span>
              <a href="#sources" className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground">
                <Library className="size-3.5" />
                {t("report.sourcesCount", { n: r.sources.length })}
              </a>
            </div>
            <h1 className="mt-4 font-display text-4xl leading-[1.15] tracking-tight text-balance md:text-5xl">
              {r.title}
            </h1>
          </header>

          {/* The sources up front, as Perplexity shows them. */}
          <div className="mt-7 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {r.sources.slice(0, 3).map((s) => (
              <button
                key={s.id}
                onClick={() => setOpen(s.id)}
                className="group flex flex-col gap-2 rounded-xl border bg-card p-3 text-left transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:bg-muted/40 hover:shadow-md active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none"
              >
                <span className="line-clamp-2 text-xs leading-snug font-medium">{s.title}</span>
                <span className="mt-auto flex items-center gap-1.5 text-[0.7rem] text-muted-foreground">
                  <Favicon url={s.url} className="size-3.5" />
                  <span className="truncate">{domainOf(s.url)}</span>
                  <Num id={s.id} className="ml-auto h-4 min-w-4 px-1 text-[0.6rem]" />
                </span>
              </button>
            ))}
            {r.sources.length > 3 && (
              <a
                href="#sources"
                className="flex flex-col justify-between gap-2 rounded-xl border bg-card p-3 text-xs transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:bg-muted/40 hover:shadow-md motion-reduce:transform-none"
              >
                <span className="flex -space-x-1">
                  {r.sources.slice(3, 8).map((s) => (
                    <Favicon key={s.id} url={s.url} className="size-4 ring-2 ring-card" />
                  ))}
                </span>
                <span className="text-muted-foreground">{t("report.sourcesCount", { n: r.sources.length })}</span>
              </a>
            )}
          </div>

          <div className="prose-report mt-10">
            {r.lead.trim() && (
              // A line down its side, not a box: an overview can run to
              // several paragraphs, and a filled card that long weighs on the page.
              <div className="border-l-2 border-brand/60 pl-5 md:pl-6">
                <p className="!mb-2 flex items-center gap-1.5 text-xs font-medium tracking-wide text-brand">
                  <BookOpen className="size-3.5" />
                  {t("report.summary")}
                </p>
                <div className="lead" dangerouslySetInnerHTML={{ __html: render(r.lead) }} />
              </div>
            )}
            <Body sections={sections} />
          </div>

          <section id="sources" className="mt-16 scroll-mt-24 border-t pt-8">
            <h2 className="mb-5 flex items-baseline gap-3 font-display text-2xl tracking-tight">
              {t("report.allSources")}
              <span className="font-sans text-sm text-muted-foreground tabular-nums">{r.sources.length}</span>
            </h2>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {r.sources.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setOpen(s.id)}
                  className="group flex flex-col gap-1.5 rounded-xl border bg-card p-3.5 text-left transition-[transform,box-shadow,background-color,border-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md active:translate-y-0 active:scale-[0.99] motion-reduce:transform-none"
                >
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Num id={s.id} />
                    <Favicon url={s.url} className="size-3.5" />
                    <span className="truncate">{domainOf(s.url)}</span>
                  </span>
                  <span className="line-clamp-2 text-sm leading-snug font-medium transition-colors group-hover:text-brand">
                    {s.title}
                  </span>
                  {s.evidence[0] && (
                    <span className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">{s.evidence[0]}</span>
                  )}
                </button>
              ))}
            </div>
          </section>
        </article>

        <aside className="hidden lg:block">
          <nav className="sticky top-20 max-h-[calc(100svh-6rem)] overflow-y-auto pb-6 text-sm">
            <p className="mb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t("report.onThisPage")}
            </p>
            <Contents sections={sections} active={active} />
            <div className="mt-5 space-y-1 border-t pt-4 text-muted-foreground">
              <a href="#sources" className="flex items-center gap-2 py-1 pl-3 transition-colors hover:text-foreground">
                <Library className="size-3.5" />
                {t("report.allSources")}
                <span className="ml-auto tabular-nums">{r.sources.length}</span>
              </a>
              <button
                type="button"
                onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
                className="flex items-center gap-2 py-1 pl-3 transition-colors hover:text-foreground"
              >
                <ArrowUp className="size-3.5" />
                {t("report.backToTop")}
              </button>
              <div className="mt-3 flex items-center gap-2 pl-3 text-xs">
                <span className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full bg-brand transition-[width] duration-150"
                    style={{ width: `${Math.round(progress * 100)}%` }}
                  />
                </span>
                <span className="w-8 text-right tabular-nums">{Math.round(progress * 100)}%</span>
              </div>
            </div>
          </nav>
        </aside>
      </div>
      )}

      {hovered && hover && <CitePreview source={hovered} at={hover.at} />}
      <SourceSheet
        source={open != null ? byId.get(open) : undefined}
        place={r.sources.findIndex((s) => s.id === open) + 1}
        total={r.sources.length}
        onClose={() => setOpen(null)}
        onStep={(by) => {
          const next = r.sources[r.sources.findIndex((s) => s.id === open) + by];
          if (next) setOpen(next.id);
        }}
      />
    </div>
  );
}

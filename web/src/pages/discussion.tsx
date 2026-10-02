// A Discussion (docs/web-app-design.md, รุ่นสอง: Discussion): the round
// table in the middle — who said what, with citations — the mind map and the
// reports on the right, and at the foot the owner's turn: speak, let the table
// go on once or three times, or write a report. Each of those is a Turn that
// waits in the queue; the page polls until it is done.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  BookOpen,
  ChevronRight,
  FileText,
  FolderInput,
  FolderOpen,
  LifeBuoy,
  Gauge,
  Globe,
  Loader2,
  MessagesSquare,
  MoreHorizontal,
  Network,
  Play,
  RotateCcw,
  SendHorizontal,
  Sparkles,
  Square,
  Trash2,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import {
  ErrorText,
  LoadingRows,
  PageHeader,
  StatusBadge,
  Toolbar,
  domainOf,
  errorMessage,
  formatDate,
} from "@/components/common";
import { QuotaLine, type Depth } from "@/components/composer";
import { MoveSessionDialog } from "@/components/move-session";
import { SupportDialog } from "@/components/support-dialog";
import { FINAL, RunNotes, Stepper, useConfirm } from "@/components/run-parts";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { has, useT, type Key } from "@/i18n";
import { useRunLive } from "@/hooks/use-run-live";
import { cn } from "@/lib/utils";

type Turn = Schemas["RunOut"];
type Discussion = Schemas["DiscussionOut"];

// What engines/costorm/engine.py `view` writes beside each finished Turn.
type ViewTurn = { role: string; role_description: string; type: string; text: string; cited: number[]; warmup: boolean };
type MindNode = { name: string; count: number; children: MindNode[] };
type Source = { url: string; title: string; snippets: string[] };
type View = { topic: string; turns: ViewTurn[]; mind_map: MindNode[]; sources: Record<string, Source>; experts: string[] };

type Asked = { action: "say" | "step" | "auto" | "report" | "start"; text?: string; steps?: number };

// --- the conversation -----------------------------------------------------------------

/** An utterance with its [n] markers as links to the sources they cite. */
function Cited({ text, sources }: { text: string; sources: Record<string, Source> }) {
  const parts = text.replace(/\*\*/g, "").split(/(\[\d+\])/);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        const source = m ? sources[m[1]] : undefined;
        if (!m) return <span key={i}>{part}</span>;
        if (!source) return null;
        return (
          <a
            key={i}
            href={source.url}
            target="_blank"
            rel="noreferrer"
            title={`${source.title} — ${domainOf(source.url)}`}
            className="mx-px align-super text-[10px] font-medium text-brand hover:underline"
          >
            [{m[1]}]
          </a>
        );
      })}
    </>
  );
}

// The same speaker keeps the same colour through the conversation.
const HUES = ["bg-sky-500", "bg-violet-500", "bg-emerald-500", "bg-amber-500", "bg-rose-500", "bg-teal-500"];
function hue(role: string) {
  let n = 0;
  for (const ch of role) n = (n * 31 + ch.charCodeAt(0)) >>> 0;
  return HUES[n % HUES.length];
}

function Utterance({ turn, sources }: { turn: ViewTurn; sources: Record<string, Source> }) {
  const { t } = useT();
  const guest = turn.role === "Guest";
  if (guest)
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm whitespace-pre-wrap text-primary-foreground">
          {turn.text}
        </div>
      </div>
    );
  const moderator = turn.role.toLowerCase().includes("moderator");
  return (
    <div className="flex gap-3">
      <span
        aria-hidden
        className={cn(
          "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white",
          moderator ? "bg-foreground/70" : hue(turn.role),
        )}
      >
        {turn.role.trim().charAt(0).toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-medium">{moderator ? t("disc.moderator") : turn.role}</span>
          {turn.role_description && (
            <span className="truncate text-xs text-muted-foreground" title={turn.role_description}>
              {turn.role_description}
            </span>
          )}
        </div>
        <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/90">
          <Cited text={turn.text} sources={sources} />
        </div>
      </div>
    </div>
  );
}

// --- a Turn in progress ------------------------------------------------------------------

function TurnProgress({ turn, onChange }: { turn: Turn; onChange: () => void }) {
  const { t } = useT();
  const [browsed, setBrowsed] = useState<string[]>([]);
  const live = turn.status === "running" || turn.status === "cancelling";
  useRunLive(turn.id, live, (d) => {
    const urls = d.events.flatMap((e) => (e.type === "note" && e.data.kind === "browsed" ? (e.data.urls as string[]) : []));
    if (urls.length) setBrowsed((prev) => [...new Set([...prev, ...urls])]);
    if (d.status !== turn.status || d.stage !== turn.stage) onChange();
  });

  const action = turn.turn?.action as Asked["action"];
  return (
    <div className="space-y-3 rounded-xl bg-muted/50 p-4">
      {action === "start" ? (
        <Stepper stage={turn.stage} status={turn.status} engine="co-storm" />
      ) : (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          {turn.status === "queued" ? t("status.queued") : t(`disc.working.${action}` as Key)}
        </div>
      )}
      {browsed.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Globe className="size-3.5" />
          {t("run.browsed", { n: browsed.length })}
          {browsed.slice(-4).map((u) => (
            <span key={u} className="max-w-48 truncate rounded-full bg-background px-2 py-0.5">
              {domainOf(u)}
            </span>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">{t("run.closeSafe")}</p>
    </div>
  );
}

/** The last Turn that did not work, with the way to ask for it again. */
function TurnFailed({ turn, onRetry, pending }: { turn: Turn; onRetry: () => void; pending: boolean }) {
  const { t } = useT();
  const reasonKey = `reason.${turn.reason}`;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusBadge status={turn.status} />
          <span className="text-muted-foreground">{t(`disc.action.${turn.turn?.action}` as Key)}</span>
        </div>
        {turn.reason && turn.reason !== "cancelled" && (
          <p className="mt-1 text-destructive">
            {has(reasonKey) ? t(reasonKey as Key) : turn.reason}
            {turn.quota_refunded && <span className="ml-2 text-xs text-muted-foreground">· {t("disc.turnBack")}</span>}
          </p>
        )}
      </div>
      <Button variant="outline" size="sm" disabled={pending} onClick={onRetry}>
        <RotateCcw />
        {t("run.retry")}
      </Button>
    </div>
  );
}

// --- the side column --------------------------------------------------------------------

function MindMap({ nodes, depth = 0 }: { nodes: MindNode[]; depth?: number }) {
  return (
    <ul className={cn("flex min-w-0 flex-col gap-0.5", depth > 0 && "mt-0.5 ml-3 border-l pl-2")}>
      {nodes.map((n, i) => (
        <li key={`${n.name}-${i}`} className="min-w-0">
          <div className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-muted/60">
            <ChevronRight className={cn("size-3 shrink-0 text-muted-foreground", !n.children.length && "opacity-0")} />
            <span className="min-w-0 flex-1 truncate" title={n.name}>
              {n.name}
            </span>
            {n.count > 0 && <span className="shrink-0 rounded bg-muted px-1.5 text-[11px] text-muted-foreground">{n.count}</span>}
          </div>
          {n.children.length > 0 && <MindMap nodes={n.children} depth={depth + 1} />}
        </li>
      ))}
    </ul>
  );
}

function SideSection({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-2">
      <h2 className="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {icon}
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Reports, the mind map and who is at the table: the side column on wide
 *  screens, a fold above the conversation on narrow ones. */
function Side({ d, view, sources }: { d: Discussion; view: View | null; sources: Record<string, Source> }) {
  const { t, lang } = useT();
  return (
    <>
    <SideSection icon={<FileText className="size-3.5" />} title={t("disc.reports")}>
      {d.reports.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("disc.noReports")}</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {[...d.reports].reverse().map((r) => (
            <li key={r.run_id} className="min-w-0">
              <Link
                to="/runs/$runId"
                params={{ runId: r.run_id }}
                className="block rounded-lg border bg-card px-3 py-2 text-sm shadow-xs transition-colors hover:bg-muted/50"
              >
                <div className="truncate font-medium">{r.title}</div>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatDate(r.finished_at, lang)}</span>
                  {r.source_count != null && (
                    <span className="flex items-center gap-1">
                      <BookOpen className="size-3" />
                      {r.source_count}
                    </span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SideSection>
    <SideSection icon={<Network className="size-3.5" />} title={t("disc.mindMap")}>
      {view?.mind_map.length ? (
        <MindMap nodes={view.mind_map} />
      ) : (
        <p className="text-sm text-muted-foreground">{t("disc.mindMapEmpty")}</p>
      )}
    </SideSection>
    {!!view?.experts.length && (
      <SideSection icon={<Users className="size-3.5" />} title={t("disc.experts")}>
        <ul className="flex flex-col gap-1.5">
          {view.experts.map((e) => (
            <li key={e} className="flex min-w-0 items-center gap-2 text-sm">
              <span className={cn("size-2 shrink-0 rounded-full", hue(e))} />
              <span className="truncate" title={e}>
                {e}
              </span>
            </li>
          ))}
        </ul>
      </SideSection>
    )}
    {d.turns.length > 0 && <RunNotes notes={d.turns[d.turns.length - 1].notes ?? {}} />}
    <p className="text-xs text-muted-foreground">{t("disc.sources", { n: Object.keys(sources).length })}</p>
    </>
  );
}

// --- the page ----------------------------------------------------------------------------

export function DiscussionPage({ sessionId }: { sessionId: string }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { confirm, dialog } = useConfirm();
  const [moving, setMoving] = useState(false);
  const [helping, setHelping] = useState(false);
  const [text, setText] = useState("");
  // A Turn waiting for the owner to agree to another quota unit.
  const [extending, setExtending] = useState<Asked | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const query = useQuery({
    queryKey: ["discussion", sessionId],
    queryFn: () => call(api.GET("/api/discussions/{session_id}", { params: { path: { session_id: sessionId } } })),
    // A waiting Turn is looked for every 3 s, to see it start; a working one tells the page itself
    // (TurnProgress, pushed), so the page only checks now and then in case it was missed.
    refetchInterval: (q) => {
      const current = q.state.data?.current;
      if (!current) return false;
      return current.status === "running" || current.status === "cancelling" ? 30000 : 3000;
    },
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["discussion", sessionId] });
    queryClient.invalidateQueries({ queryKey: ["quota"] });
    queryClient.invalidateQueries({ queryKey: ["recent"] });
  };
  const ask = useMutation({
    mutationFn: ({ asked, extend }: { asked: Asked; extend?: boolean }) =>
      call(
        api.POST("/api/discussions/{session_id}/turns", {
          params: { path: { session_id: sessionId } },
          body: { action: asked.action, text: asked.text ?? "", steps: asked.steps ?? 3, extend: !!extend },
        }),
      ),
    onSuccess: (_, { asked }) => {
      if (asked.action === "say") setText("");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e, t)),
  });
  const cancel = useMutation({
    mutationFn: (runId: string) => call(api.POST("/api/runs/{run_id}/cancel", { params: { path: { run_id: runId } } })),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e, t)),
  });
  const remove = useMutation({
    mutationFn: () => call(api.DELETE("/api/sessions/{session_id}", { params: { path: { session_id: sessionId } } })),
    onSuccess: () => {
      const projectId = query.data?.project_id;
      toast.success(t("common.deleted"));
      queryClient.invalidateQueries();
      if (projectId) navigate({ to: "/projects/$projectId", params: { projectId } });
      else navigate({ to: "/research" });
    },
  });

  const d: Discussion | undefined = query.data;
  const view = (d?.view ?? null) as View | null;
  const conversation = view?.turns ?? [];
  const warmup = conversation.filter((x) => x.warmup);
  const later = conversation.filter((x) => !x.warmup);
  // After the conversation grows, keep its newest line in sight.
  useEffect(() => {
    if (later.length) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [later.length, d?.current?.id]);

  // The last Turn after the last finished one, if it did not work.
  const failed = useMemo(() => {
    if (!d || d.current) return null;
    const last = d.turns[d.turns.length - 1];
    return last && last.status !== "succeeded" && FINAL.has(last.status) ? last : null;
  }, [d]);

  if (query.isLoading)
    return (
      <div className="p-8">
        <LoadingRows />
      </div>
    );
  if (!d)
    return (
      <div className="p-8">
        <ErrorText error={query.error} />
      </div>
    );

  const started = !!view;
  const busy = !!d.current || ask.isPending;
  const exhausted = d.allowance.remaining === 0;
  const go = (asked: Asked) => (exhausted ? setExtending(asked) : ask.mutate({ asked }));
  const sources = view?.sources ?? {};
  const pendingSay = d.current?.turn?.action === "say" ? (d.current.turn.text as string) : null;

  return (
    <div className="flex min-h-0 flex-1">
      {dialog}
      <MoveSessionDialog
        session={moving ? { id: d.id, title: d.title, project_id: d.project_id } : null}
        onOpenChange={setMoving}
      />
      {!d.read_only && <SupportDialog sessionId={d.id} open={helping} onOpenChange={setHelping} />}
      <AlertDialog open={!!extending} onOpenChange={(open) => !open && setExtending(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("disc.extendTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("disc.extendText", { n: d.allowance.per_block })}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (extending) ask.mutate({ asked: extending, extend: true });
                setExtending(null);
              }}
            >
              {t("disc.extend")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mx-auto w-full max-w-3xl flex-1 px-6 pt-8 pb-6">
          <Toolbar>
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden sm:inline-flex">
                  <BreadcrumbLink asChild>
                    {d.project_id ? (
                      <Link to="/projects/$projectId" params={{ projectId: d.project_id }}>
                        {d.project_name}
                      </Link>
                    ) : (
                      <Link to="/research">{t("nav.allResearch")}</Link>
                    )}
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:inline-flex" />
                <BreadcrumbItem>
                  <BreadcrumbPage className="max-w-72 truncate">{d.title}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </Toolbar>
          <PageHeader
            title={d.title}
            eyebrow={
              <button
                type="button"
                onClick={() => setMoving(true)}
                className="inline-flex items-center gap-1.5 hover:text-foreground"
              >
                <FolderOpen className="size-3.5" />
                {d.project_name ?? t("move.none")}
              </button>
            }
            actions={
              d.read_only ? (
                <span className="rounded-md bg-warning-soft px-2 py-1 text-xs text-warning">{t("support.readOnly")}</span>
              ) : (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon" aria-label={t("run.more")}>
                    <MoreHorizontal />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setMoving(true)}>
                    <FolderInput />
                    {t("move.title")}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setHelping(true)}>
                    <LifeBuoy />
                    {t("support.title")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => confirm(t("delete.confirmSession"), () => remove.mutate())}
                  >
                    <Trash2 />
                    {t("delete.session")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              )
            }
          />
          <div className="-mt-5 mb-8 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="rounded-md bg-muted px-1.5 py-0.5 font-medium text-foreground/80">Co-STORM</span>
            <span className="flex items-center gap-1">
              <Globe className="size-3" />
              {d.language === "th" ? t("lang.th") : t("lang.en")}
            </span>
            <span className="flex items-center gap-1">
              <Sparkles className="size-3" />
              {d.model_label}
            </span>
            <span>{d.search_label}</span>
            <span className="flex items-center gap-1">
              <Gauge className="size-3" />
              {t(`depth.${d.depth as Depth}`)}
            </span>
            <span className={cn("flex items-center gap-1", exhausted && "text-warning")}>
              <MessagesSquare className="size-3" />
              {t("disc.turnsLeft", { n: d.allowance.remaining, total: d.allowance.per_block * Math.max(1, d.allowance.blocks) })}
            </span>
          </div>

          {started && (
            <details className="mb-6 rounded-xl border px-4 py-3 lg:hidden">
              <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium select-none">
                <Network className="size-4 text-muted-foreground" />
                {t("disc.side", { n: d.reports.length })}
              </summary>
              <div className="mt-4 space-y-6">
                <Side d={d} view={view} sources={sources} />
              </div>
            </details>
          )}
          {/* Before the warm start has finished there is nothing to read yet. */}
          {!started && d.current && <TurnProgress turn={d.current} onChange={refresh} />}
          {!started && !d.current && failed && (
            <TurnFailed turn={failed} pending={ask.isPending} onRetry={() => ask.mutate({ asked: { action: "start" } })} />
          )}

          {started && (
            <div className="space-y-6">
              {warmup.length > 0 && (
                <details className="group rounded-xl border bg-muted/30 px-4 py-3" open={later.length === 0}>
                  <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium select-none">
                    <ChevronRight className="size-4 transition-transform group-open:rotate-90" />
                    {t("disc.warmup", { n: warmup.length })}
                  </summary>
                  <p className="mt-2 mb-4 text-xs text-muted-foreground">{t("disc.warmupLead")}</p>
                  <div className="space-y-5">
                    {warmup.map((x, i) => (
                      <Utterance key={i} turn={x} sources={sources} />
                    ))}
                  </div>
                </details>
              )}
              {later.map((x, i) => (
                <Utterance key={i} turn={x} sources={sources} />
              ))}
              {pendingSay && (
                <Utterance turn={{ role: "Guest", role_description: "", type: "", text: pendingSay, cited: [], warmup: false }} sources={sources} />
              )}
              {d.current && (
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <TurnProgress turn={d.current} onChange={refresh} />
                  </div>
                  {!FINAL.has(d.current.status) && d.current.status !== "cancelling" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("run.cancel")}
                      disabled={cancel.isPending}
                      onClick={() => cancel.mutate(d.current!.id)}
                    >
                      <Square />
                    </Button>
                  )}
                </div>
              )}
              {failed && (
                <TurnFailed
                  turn={failed}
                  pending={ask.isPending}
                  onRetry={() => go(failed.turn as Asked)}
                />
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>

        {/* The owner's turn, at the foot of the page. */}
        {started && !d.read_only && (
          <div className="sticky bottom-0 border-t bg-background/90 backdrop-blur">
            <form
              className="mx-auto w-full max-w-3xl space-y-2 px-6 py-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (text.trim() && !busy) go({ action: "say", text: text.trim() });
              }}
            >
              <div className="flex items-end gap-2 rounded-xl border bg-card p-2 shadow-xs">
                <Textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      if (text.trim() && !busy) go({ action: "say", text: text.trim() });
                    }
                  }}
                  placeholder={t(busy ? "disc.placeholderBusy" : "disc.placeholder")}
                  maxLength={2000}
                  className="min-h-10 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
                />
                <Button type="submit" size="icon" className="size-9 shrink-0 rounded-lg" disabled={busy || !text.trim()} aria-label={t("disc.send")}>
                  {ask.isPending && ask.variables?.asked.action === "say" ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => go({ action: "step" })}>
                  <Play />
                  {t("disc.step")}
                </Button>
                <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => go({ action: "auto", steps: 3 })}>
                  <Users />
                  {t("disc.auto")}
                </Button>
                <Button type="button" size="sm" disabled={busy} onClick={() => go({ action: "report" })}>
                  <FileText />
                  {t("disc.report")}
                </Button>
                <QuotaLine className="ml-auto" />
              </div>
            </form>
          </div>
        )}
      </div>

      <aside className="sticky top-16 hidden h-[calc(100svh-4rem)] w-80 shrink-0 space-y-7 overflow-x-hidden overflow-y-auto border-l p-5 lg:block">
        <Side d={d} view={view} sources={sources} />
      </aside>
    </div>
  );
}

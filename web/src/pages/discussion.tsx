// A Discussion (docs/web-app-design.md, รุ่นสอง: Discussion): the discussion
// at a glance first (the 3D round table of components/agent-observatory-3d),
// the reports under it, then the transcript, folded to its last lines; on the
// right two cards, who is at the table and the mind map, picked in step with
// the table; at the foot the owner's turn: speak, let the table go on once or
// three times, or write a report. Each of those is a Turn that waits in the
// queue; the page polls until it is done.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  Database,
  FileText,
  FolderInput,
  FolderOpen,
  Gauge,
  Globe,
  Layers,
  Loader2,
  MessageCircle,
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
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
import { KindTag, RoomPeople, initial, isFixed, tone, useRoom, type Room } from "@/components/costorm-room";
import { MoveSessionDialog } from "@/components/move-session";
import { FailureNote, FINAL, RunNotes, useConfirm } from "@/components/run-parts";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useT, type Key } from "@/i18n";
import { useRunLive } from "@/hooks/use-run-live";
import { modelHtml } from "@/lib/model-markdown";
import { cn } from "@/lib/utils";

// three.js comes only with the 3D table, when someone opens it.
const CoStormObservatory3D = lazy(() =>
  import("@/components/agent-observatory-3d").then((m) => ({ default: m.CoStormObservatory3D })),
);

type Turn = Schemas["RunOut"];
type Discussion = Schemas["DiscussionOut"];

// What engines/costorm/engine.py `view` writes beside each finished Turn.
type ViewTurn = { role: string; role_description: string; type: string; text: string; cited: number[]; warmup: boolean };
type Source = { url: string; title: string; snippets: string[] };
type View = { topic: string; turns: ViewTurn[]; mind_map: MindNode[]; sources: Record<string, Source>; experts: string[] };

const NO_EXPERTS: string[] = [];

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

/** Who said it, in the reader's words: Co-STORM's own role names stay out of sight. */
function speakerName(role: string, t: ReturnType<typeof useT>["t"]) {
  const r = role.toLowerCase();
  if (r.includes("moderator")) return t("disc.moderator");
  if (role === "General Knowledge Provider") return t("room.gkp");
  if (r.startsWith("background discussion expert")) return t("obs3d.bgExpert");
  return role;
}

// Past this many letters an utterance shows its first lines until opened.
const LONG = 420;

/** One utterance. A question stands out as a card of its own, so the talk reads
 *  as question and answers; an answer is rendered markdown, its [n] markers
 *  small links to their sources, and a long one folded to its first lines. */
function Utterance({ turn, sources }: { turn: ViewTurn; sources: Record<string, Source> }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  if (turn.role === "Guest")
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm whitespace-pre-wrap text-primary-foreground">
          {turn.text}
        </div>
      </div>
    );
  const name = speakerName(turn.role, t);
  const question = turn.type === "Original Question" || turn.role.toLowerCase().includes("moderator");
  const html = modelHtml(turn.text, (n) => sources[String(n)]);
  const long = turn.text.length > LONG;
  const avatar = (
    <span
      aria-hidden
      className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
      style={{ background: tone(turn.role) }}
    >
      {initial(name)}
    </span>
  );
  if (question)
    return (
      <div className="rounded-xl border bg-muted/40 px-4 py-3">
        <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
          {avatar}
          <span className="font-medium text-foreground">{name}</span>
          <span>{t("room.asks")}</span>
        </div>
        <div className="md-body text-[15px] leading-relaxed font-medium" dangerouslySetInnerHTML={{ __html: html }} />
      </div>
    );
  // An answer is the usual thing to say; only another kind is worth a tag.
  const tagged = turn.type && turn.type !== "Potential Answer";
  return (
    <div className="flex gap-3 pl-1 sm:pl-4">
      {avatar}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
          <span className="font-medium">{name}</span>
          {tagged && <KindTag type={turn.type} />}
          {turn.role_description && (
            <span className="truncate text-xs text-muted-foreground" title={turn.role_description}>
              {turn.role_description}
            </span>
          )}
        </div>
        <div
          className={cn("md-body max-w-prose text-sm leading-7 text-foreground/90", long && !open && "line-clamp-5")}
          dangerouslySetInnerHTML={{ __html: html }}
        />
        {long && (
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="mt-1 text-xs font-medium text-brand hover:underline"
          >
            {t(open ? "room.readLess" : "room.readMore")}
          </button>
        )}
      </div>
    </div>
  );
}

// --- a Turn in progress ------------------------------------------------------------------

function TurnProgress({ turn, onChange }: { turn: Turn; onChange: () => void }) {
  const { t } = useT();
  const [browsed, setBrowsed] = useState<string[]>([]);
  // How far the warm start has got (engines/costorm: its four steps, as notes).
  const [step, setStep] = useState(0);
  const live = turn.status === "running" || turn.status === "cancelling";
  useRunLive(turn.id, live, (d) => {
    const urls = d.events.flatMap((e) => (e.type === "note" && e.data.kind === "browsed" ? (e.data.urls as string[]) : []));
    if (urls.length) setBrowsed((prev) => [...new Set([...prev, ...urls])]);
    const steps = d.events.flatMap((e) => (e.type === "note" && e.data.kind === "warmup" && e.data.step ? [Number(e.data.step)] : []));
    if (steps.length) setStep((s) => Math.max(s, ...steps));
    if (d.status !== turn.status || d.stage !== turn.stage) onChange();
  });

  const action = turn.turn?.action as Asked["action"];
  return (
    <div className="space-y-3 rounded-xl bg-muted/50 p-4">
      {action === "start" ? (
        <WarmSteps step={turn.status === "queued" ? 0 : Math.max(1, step)} />
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

/** The warm start's four steps as they happen, and the first report it leads to. */
function WarmSteps({ step }: { step: number }) {
  const { t } = useT();
  const labels: Key[] = ["warm.step1", "warm.step2", "warm.step3", "warm.step4", "warm.report"];
  return (
    <ol className="space-y-1.5 text-sm">
      {labels.map((label, i) => {
        const state = i + 1 < step ? "done" : i + 1 === step ? "now" : "todo";
        return (
          <li key={label} className={cn("flex items-center gap-2", state === "todo" && "text-muted-foreground", state === "now" && "font-medium text-brand")}>
            {state === "done" ? (
              <Check className="size-4 text-success" />
            ) : state === "now" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Circle className="size-4" />
            )}
            {t(label)}
          </li>
        );
      })}
    </ol>
  );
}

/** The last Turn that did not work, with the way to ask for it again. */
function TurnFailed({ turn, onRetry, pending }: { turn: Turn; onRetry: () => void; pending: boolean }) {
  const { t } = useT();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusBadge status={turn.status} />
          <span className="text-muted-foreground">{t(`disc.action.${turn.turn?.action}` as Key)}</span>
        </div>
        {/* Already in the Turn's red box. */}
        <FailureNote run={turn} refunded="disc.turnBack" className="mt-1 bg-transparent p-0" />
      </div>
      <Button variant="outline" size="sm" disabled={pending} onClick={onRetry}>
        <RotateCcw />
        {t("run.retry")}
      </Button>
    </div>
  );
}

// --- the side column --------------------------------------------------------------------

type MindNode = { name: string; count: number; children: MindNode[] };

/** A top topic's colour in the mind map, and its key in the room's one selection. */
const TOPIC_TONES = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#14b8a6", "#ef4444"];
const topicTone = (i: number) => TOPIC_TONES[i % TOPIC_TONES.length];
const topicKey = (i: number) => `topic:${i}`;

/** What a topic holds, its subtopics included. */
const held = (n: MindNode): number => n.count + n.children.reduce((a, c) => a + held(c), 0);
const nodeCount = (nodes: MindNode[]): number => nodes.reduce((a, n) => a + 1 + nodeCount(n.children), 0);

function SubTopics({ nodes }: { nodes: MindNode[] }) {
  return (
    <ul className="mt-0.5 ml-3 flex min-w-0 flex-col gap-0.5 border-l pl-2">
      {nodes.map((n, i) => (
        <li key={`${n.name}-${i}`} className="min-w-0">
          <div className="flex items-start gap-2 px-1.5 py-1 text-xs text-foreground/85">
            <span className="min-w-0 flex-1 leading-snug">{n.name}</span>
            {held(n) > 0 && <span className="shrink-0 rounded-full bg-muted px-1.5 text-[11px] text-muted-foreground">{held(n)}</span>}
          </div>
          {n.children.length > 0 && <SubTopics nodes={n.children} />}
        </li>
      ))}
    </ul>
  );
}

/** A card of the side column, folded by its heading. */
function SideCard({
  icon,
  tint,
  title,
  count,
  lead,
  open,
  onToggle,
  children,
}: {
  icon: ReactNode;
  tint: string;
  title: string;
  count?: ReactNode;
  lead: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-2xl border bg-card p-3 shadow-xs">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-center gap-2.5 rounded-lg p-1 text-left transition-colors hover:bg-muted/40"
      >
        <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", tint)}>{icon}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold">
            {title}
            {count != null && <span className="font-normal text-muted-foreground"> · {count}</span>}
          </span>
          <span className="block text-xs text-muted-foreground">{lead}</span>
        </span>
        <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform", !open && "-rotate-90")} />
      </button>
      {open && <div className="mt-2 border-t pt-3">{children}</div>}
    </section>
  );
}

/** Who is at the table. Opens by itself when someone is picked on the map. */
function PeopleCard({ room, sources }: { room: Room; sources: Record<string, Source> }) {
  const { t } = useT();
  const [open, setOpen] = useState(true);
  useEffect(() => {
    if (room.picked && !room.picked.startsWith("topic:")) setOpen(true);
  }, [room.picked]);
  return (
    <SideCard
      icon={<Users className="size-4" />}
      tint="bg-brand-soft text-brand"
      title={t("room.people")}
      count={room.seats.length}
      lead={t("room.peopleLead")}
      open={open}
      onToggle={() => setOpen((o) => !o)}
    >
      <RoomPeople room={room} renderText={(text) => <Cited text={text} sources={sources} />} />
    </SideCard>
  );
}

/** The mind map: its top topics in the map's colours, each pickable as on the
 *  map, and every source the table has collected. */
function MindMapCard({ view, room, sources }: { view: View; room: Room; sources: Record<string, Source> }) {
  const { t } = useT();
  const [open, setOpen] = useState(true);
  const [mainOnly, setMainOnly] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  useEffect(() => {
    if (room.picked?.startsWith("topic:")) setOpen(true);
  }, [room.picked]);
  const listed = Object.entries(sources).sort(([a], [b]) => Number(a) - Number(b));
  return (
    <SideCard
      icon={<Network className="size-4" />}
      tint="bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
      title={t("disc.mindMap")}
      count={view.mind_map.length ? t("map.topicsN", { n: nodeCount(view.mind_map) }) : undefined}
      lead={t("room.mapLead")}
      open={open}
      onToggle={() => setOpen((o) => !o)}
    >
      {view.mind_map.length ? (
        <div className="space-y-1">
          <div className="flex items-center justify-end gap-2 pb-1">
            <label htmlFor="disc-main-only" className="text-xs text-muted-foreground">
              {t("room.mainOnly")}
            </label>
            <Switch id="disc-main-only" size="sm" checked={mainOnly} onCheckedChange={setMainOnly} />
          </div>
          <ul className="flex flex-col">
            {view.mind_map.map((n, i) => {
              const key = topicKey(i);
              const picked = room.picked === key;
              return (
                <li key={`${n.name}-${i}`} className="border-b py-1 last:border-b-0">
                  <button
                    type="button"
                    aria-pressed={picked}
                    onClick={() => room.pick(key)}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-lg border px-1.5 py-1.5 text-left text-sm font-medium transition-[background-color,box-shadow]",
                      picked ? "border-brand bg-brand/5 ring-3 ring-brand/15" : "border-transparent hover:bg-muted/50",
                    )}
                  >
                    <span aria-hidden className="mt-1.5 size-2.5 shrink-0 rounded-full" style={{ background: topicTone(i) }} />
                    <span className="min-w-0 flex-1 leading-snug">{n.name}</span>
                    {held(n) > 0 && (
                      <span className="shrink-0 rounded-full bg-muted px-1.5 text-[11px] font-semibold text-muted-foreground">{held(n)}</span>
                    )}
                  </button>
                  {!mainOnly && n.children.length > 0 && <SubTopics nodes={n.children} />}
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("disc.mindMapEmpty")}</p>
      )}
      {listed.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            aria-expanded={sourcesOpen}
            onClick={() => setSourcesOpen((o) => !o)}
            className="flex w-full items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-left text-sm font-medium transition-colors hover:bg-muted"
          >
            <BookOpen className="size-4 text-muted-foreground" />
            <span className="flex-1">
              {t("room.sourcesAll")} <span className="font-normal text-muted-foreground">{t("map.citedN", { n: listed.length })}</span>
            </span>
            <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", !sourcesOpen && "-rotate-90")} />
          </button>
          {sourcesOpen && (
            <ol className="mt-2 max-h-80 space-y-1 overflow-y-auto pr-1">
              {listed.map(([n, s]) => (
                <li key={n}>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex gap-2 rounded-md px-2 py-1 text-xs hover:bg-muted/60"
                  >
                    <span className="shrink-0 text-muted-foreground tabular-nums">[{n}]</span>
                    <span className="min-w-0">
                      <span className="line-clamp-2 text-foreground/90">{s.title || s.url}</span>
                      <span className="text-muted-foreground">{domainOf(s.url)}</span>
                    </span>
                  </a>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </SideCard>
  );
}

/** The side column's cards: beside the page on wide screens, under the reports on narrow ones. */
function SideCards({ view, room, sources }: { view: View; room: Room; sources: Record<string, Source> }) {
  return (
    <>
      <PeopleCard room={room} sources={sources} />
      <MindMapCard view={view} room={room} sources={sources} />
    </>
  );
}

/** The Discussion's reports, in the middle of the page under the table: the
 *  newest first and largest, the one being written as it is written (the first
 *  one by itself, after the warm start). */
function Reports({ d }: { d: Discussion }) {
  const { t, lang } = useT();
  const writing = d.current?.turn?.action === "report" && !FINAL.has(d.current.status);
  if (!d.reports.length && !writing) return null;
  const [latest, ...older] = [...d.reports].reverse();
  return (
    <section aria-labelledby="disc-reports" className="space-y-2">
      <h2 id="disc-reports" className="flex items-center gap-2 text-sm font-semibold">
        <FileText className="size-4 text-muted-foreground" />
        {t("disc.reports")}
        {d.reports.length > 0 && <span className="font-normal text-muted-foreground">{d.reports.length}</span>}
      </h2>
      {writing && (
        <div className="flex items-center gap-3 rounded-2xl border border-dashed bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          {t(d.current?.turn?.auto ? "disc.working.reportFirst" : "disc.working.report")}
        </div>
      )}
      {latest && (
        <Link
          to="/runs/$runId"
          params={{ runId: latest.run_id }}
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card px-4 py-3.5 shadow-xs transition-colors hover:bg-muted/40"
        >
          <span className="min-w-0">
            <span className="block truncate font-medium">{latest.title}</span>
            <span className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
              <span>{t("disc.reportLatest")} · {formatDate(latest.finished_at, lang)}</span>
              {latest.source_count != null && (
                <span className="flex items-center gap-1">
                  <BookOpen className="size-3" />
                  {latest.source_count}
                </span>
              )}
            </span>
          </span>
          <span className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-sm font-medium text-primary-foreground">
            {t("disc.readReport")}
            <ChevronRight className="size-4" />
          </span>
        </Link>
      )}
      {older.length > 0 && (
        <ul className="flex flex-col gap-1">
          {older.map((r) => (
            <li key={r.run_id}>
              <Link
                to="/runs/$runId"
                params={{ runId: r.run_id }}
                className="flex items-center justify-between gap-3 rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
              >
                <span className="truncate">{r.title}</span>
                <span className="shrink-0 text-xs">{formatDate(r.finished_at, lang)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// --- the page ----------------------------------------------------------------------------

export function DiscussionPage({ sessionId }: { sessionId: string }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { confirm, dialog } = useConfirm();
  const [moving, setMoving] = useState(false);
  // The transcript shows its last lines until opened; the round table above it is the page's subject.
  const [chatOpen, setChatOpen] = useState(false);
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
  const room = useRoom(conversation, view?.experts ?? NO_EXPERTS);
  // With the transcript open, keep its newest line in sight as it grows.
  useEffect(() => {
    if (chatOpen && later.length) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatOpen, later.length, d?.current?.id]);

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
  // The warm start at work: no view yet, but the table can already be watched filling.
  const warming = !started && !!d.current && (d.current.status === "running" || d.current.status === "cancelling");
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
        <div className="mx-auto w-full max-w-5xl flex-1 px-6 pt-8 pb-6">
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
                <span className="rounded-md bg-warning-soft px-2 py-1 text-xs text-warning">{t("run.readOnly")}</span>
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
          <div className="-mt-5 mb-6 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5 rounded-lg bg-brand-soft px-2.5 py-1 font-semibold text-brand">
              <Layers className="size-3.5" />
              Co-STORM
            </span>
            <span className="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1">
              <Globe className="size-3.5" />
              {d.language === "th" ? t("lang.th") : t("lang.en")}
            </span>
            <span className="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1">
              <Sparkles className="size-3.5" />
              {d.model_label}
            </span>
            <span className="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1">
              <Gauge className="size-3.5" />
              {t(`depth.${d.depth as Depth}`)}
            </span>
          </div>

          {/* The discussion at a glance: the 3D round table, with what it holds above it; while the
              warm start works, the table as it fills, what it reads arriving as it reads it. */}
          {(view || warming) && (
            <section aria-labelledby="disc-map" className="mb-6 space-y-3 rounded-2xl border bg-card p-4 shadow-xs">
              <h2 id="disc-map" className="flex items-center gap-2 text-sm font-semibold">
                <Network className="size-4 text-muted-foreground" />
                {t("map.title")}
              </h2>
              {view && (
              <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3">
                {[
                  { icon: Users, label: t("map.experts"), value: t("map.roles", { n: room.seats.filter((s) => !isFixed(s.role)).length }) },
                  { icon: Layers, label: t("map.topics"), value: t("map.topicsN", { n: nodeCount(view.mind_map) }) },
                  { icon: Database, label: t("map.cited"), value: t("map.citedN", { n: new Set(conversation.flatMap((x) => x.cited)).size }) },
                ].map(({ icon: Icon, label, value }) => (
                  <div key={label} className="flex items-center gap-2.5 bg-muted/40 px-3 py-2.5 dark:bg-muted/20">
                    <Icon className="size-5 shrink-0 text-brand" />
                    <div className="min-w-0">
                      <dt className="text-xs text-muted-foreground">{label}</dt>
                      <dd className="text-sm font-semibold">{value}</dd>
                    </div>
                  </div>
                ))}
              </dl>
              )}
              <Suspense fallback={<p className="text-xs text-muted-foreground">{t("obs3d.loading")}</p>}>
                <CoStormObservatory3D
                  view={view}
                  topic={d.title}
                  currentId={d.current?.id ?? null}
                  live={!!d.current && !FINAL.has(d.current.status)}
                  picked={room.picked?.startsWith("topic:") ? null : room.picked}
                  onPick={(role) => (role ? room.pick(role) : room.picked && room.pick(room.picked))}
                />
              </Suspense>
            </section>
          )}
          {/* The reports right under the map, where the owner is looking while the table works:
              the first one is written by itself after the warm start, and lands here. */}
          {started && (d.reports.length > 0 || d.current?.turn?.action === "report") && (
            <div className="mb-6">
              <Reports d={d} />
            </div>
          )}
          {/* On narrow screens the side column's cards come here. */}
          {started && view && (
            <div className="mb-6 space-y-4 lg:hidden">
              <SideCards view={view} room={room} sources={sources} />
            </div>
          )}
          {/* Before the warm start has finished there is nothing to read yet. */}
          {!started && d.current && <TurnProgress turn={d.current} onChange={refresh} />}
          {!started && !d.current && failed && (
            <TurnFailed turn={failed} pending={ask.isPending} onRetry={() => ask.mutate({ asked: { action: "start" } })} />
          )}

          {started && (
            <section aria-labelledby="disc-chat" className="space-y-6 rounded-2xl border bg-card p-4 shadow-xs">
              <div className="flex items-center justify-between gap-2">
                <h2 id="disc-chat" className="flex items-center gap-2 text-sm font-semibold">
                  <MessageCircle className="size-4 text-muted-foreground" />
                  {t("room.chat")}
                  <span className="font-normal text-muted-foreground">
                    {later.length === 0 && warmup.length > 0
                      ? t("room.chatWarmOnly", { n: warmup.length })
                      : chatOpen || later.length <= 3
                      ? t("room.chatAll", { n: later.length })
                      : t("room.chatRecent", { n: 3, total: later.length })}
                  </span>
                </h2>
                {(later.length > 3 || warmup.length > 0) && (
                  <Button variant="link" size="sm" className="h-auto px-0" aria-expanded={chatOpen} onClick={() => setChatOpen((o) => !o)}>
                    {t(chatOpen ? "room.fold" : "room.chatAllLink")}
                    {!chatOpen && <ArrowRight />}
                  </Button>
                )}
              </div>
              {!chatOpen && later.length === 0 && !pendingSay && !d.current && !failed && (
                <p className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
                  <MessageCircle className="size-4" />
                  {t("room.chatEmpty")}
                </p>
              )}
              {chatOpen && warmup.length > 0 && (
                <details className="group border-t pt-3" open={later.length === 0}>
                  <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium select-none">
                    <ChevronRight className="size-4 transition-transform group-open:rotate-90" />
                    {t("disc.warmup", { n: warmup.length })}
                  </summary>
                  <p className="mt-1 mb-4 pl-6 text-xs text-muted-foreground">{t("disc.warmupLead")}</p>
                  <div className="space-y-4">
                    {warmup.map((x, i) => (
                      <Utterance key={i} turn={x} sources={sources} />
                    ))}
                  </div>
                </details>
              )}
              {(chatOpen ? later : later.slice(-3)).map((x, i) => (
                <Utterance key={chatOpen ? i : later.length - Math.min(3, later.length) + i} turn={x} sources={sources} />
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
            </section>
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
                <Button
                  type="button"
                  size="sm"
                  disabled={busy || !d.report_ready}
                  title={!d.report_ready && !busy ? t("disc.reportUpToDate") : undefined}
                  onClick={() => go({ action: "report" })}
                >
                  <FileText />
                  {t("disc.report")}
                </Button>
                {!d.report_ready && !busy && d.reports.length > 0 && (
                  <span className="text-xs text-muted-foreground">{t("disc.reportUpToDate")}</span>
                )}
                <QuotaLine className="ml-auto" />
              </div>
            </form>
          </div>
        )}
      </div>

      <aside className="sticky top-16 hidden h-[calc(100svh-4rem)] w-96 shrink-0 space-y-4 overflow-x-hidden overflow-y-auto p-4 lg:block">
        {view && <SideCards view={view} room={room} sources={sources} />}
        {d.turns.length > 0 && <RunNotes notes={d.turns[d.turns.length - 1].notes ?? {}} />}
      </aside>
    </div>
  );
}

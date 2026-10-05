// Agent Research's loop drawn as the library's own README draws it (IterativeResearcher and
// DeepResearcher flows), lit as the Run goes: the agent at work, the edge the work travels, and a
// ring that turns through the round's four steps. Built from the Run's "flow" notes
// (server: engines/agent/flow.py). The agents' words are shown as they wrote them, in English.
import "@xyflow/react/dist/style.css";

import { useQuery } from "@tanstack/react-query";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import {
  ArrowLeft,
  Brain,
  Check,
  Globe,
  ListChecks,
  Loader2,
  Map as MapIcon,
  Network,
  PenLine,
  ScanSearch,
  type LucideIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { api, call, type Schemas } from "@/api/client";
import { Favicon, domainOf } from "@/components/common";
import { useRunLive } from "@/hooks/use-run-live";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

// --- the notes, folded into what the canvas shows ------------------------------------------

type Query = { agent: string; query: string; site?: string | null };
type FlowNote = {
  event: string;
  lane?: string;
  round?: number;
  max?: number;
  phase?: string;
  text?: string;
  gap?: string;
  complete?: boolean;
  queries?: Query[];
  sources?: number;
  urls?: string[];
  sections?: { id: string; title: string }[];
};
type Round = { round: number; observed?: string; gap?: string; complete?: boolean; queries: Query[]; sources?: number; urls: string[] };
type Lane = { id: string; title?: string; max: number; phase?: string; rounds: Round[]; writing: boolean };
type Model = { sections: { id: string; title: string }[]; lanes: Record<string, Lane>; composing: boolean };

const STEPS = ["observe", "gap", "select", "search"] as const;

function fold(notes: FlowNote[]): Model {
  const model: Model = { sections: [], lanes: {}, composing: false };
  const lane = (id = "main") =>
    (model.lanes[id] ??= { id, title: model.sections.find((s) => s.id === id)?.title, max: 0, rounds: [], writing: false });
  const round = (l: Lane, n?: number) => {
    let r = l.rounds.find((x) => x.round === n);
    if (!r) l.rounds.push((r = { round: n ?? l.rounds.length + 1, queries: [], urls: [] }));
    return r;
  };
  for (const n of notes) {
    if (n.event === "plan") {
      model.sections = n.sections ?? [];
      for (const s of model.sections) lane(s.id).title = s.title;
    } else if (n.event === "compose") model.composing = true;
    else {
      const l = lane(n.lane);
      if (n.event === "round") {
        l.max = n.max ?? l.max;
        round(l, n.round);
        l.phase = "observe";
      } else if (n.event === "phase") l.phase = n.phase;
      else if (n.event === "observed") round(l, n.round).observed = n.text;
      else if (n.event === "gap") Object.assign(round(l, n.round), { gap: n.gap, complete: n.complete });
      else if (n.event === "tasks") round(l, n.round).queries = n.queries ?? [];
      else if (n.event === "found") Object.assign(round(l, n.round), { sources: n.sources, urls: n.urls ?? [] });
      else if (n.event === "write") Object.assign(l, { writing: true, phase: "write" });
    }
  }
  return model;
}

// --- nodes and edges ----------------------------------------------------------------------

type StepState = "idle" | "rest" | "active" | "done";
type StepData = { title: string; caption: string; icon: LucideIcon; state: StepState; detail?: string; urls?: string[] };

function StepNode({ data }: NodeProps<Node<StepData>>) {
  const Icon = data.icon;
  return (
    <div
      className={cn(
        "w-[200px] rounded-xl border bg-card px-3 py-2.5 text-xs shadow-xs transition-[border-color,box-shadow,opacity] duration-300",
        data.state === "active" && "border-brand/60 ring-4 ring-brand/10",
        data.state === "idle" && "opacity-50",
      )}
    >
      <Handle type="target" position={Position.Left} id="in" className="!border-0 !bg-transparent" />
      <Handle type="source" position={Position.Right} id="out" className="!border-0 !bg-transparent" />
      <Handle type="source" position={Position.Bottom} id="down" className="!border-0 !bg-transparent" />
      <Handle type="target" position={Position.Bottom} id="back" className="!border-0 !bg-transparent" />
      <Handle type="source" position={Position.Top} id="exit" className="!border-0 !bg-transparent" />
      <Handle type="target" position={Position.Top} id="enter" className="!border-0 !bg-transparent" />
      <div className="flex items-center gap-2">
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand">
          <Icon className="size-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">{data.title}</div>
          <div className="truncate text-[10px] text-muted-foreground">{data.caption}</div>
        </div>
        {data.state === "active" && <Loader2 className="size-3.5 shrink-0 animate-spin text-brand motion-reduce:animate-none" />}
        {data.state === "done" && <Check className="size-3.5 shrink-0 text-success" />}
      </div>
      {data.detail && <div className="mt-1.5 line-clamp-2 text-[11px] leading-snug text-muted-foreground">{data.detail}</div>}
      {!!data.urls?.length && (
        <div className="mt-1.5 flex -space-x-1">
          {data.urls.slice(0, 6).map((u) => (
            <Favicon key={u} url={u} className="size-4 ring-2 ring-card" />
          ))}
        </div>
      )}
    </div>
  );
}

/** The round's ring: four dots for its steps, the current one lit, an arc turning while it works. */
type HubData = { round: number; max: number; step: number; spinning: boolean; done: boolean; size?: number };

function Ring({ round, max, step, spinning, done, size = 92 }: HubData) {
  const { t } = useT();
  const c = size / 2;
  const r = c - 7;
  const dots = [-90, 0, 90, 180].map((deg) => [c + r * Math.cos((deg * Math.PI) / 180), c + r * Math.sin((deg * Math.PI) / 180)]);
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="absolute inset-0">
        <circle cx={c} cy={c} r={r} fill="none" stroke="var(--color-border)" strokeWidth={1.5} />
        {dots.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={size > 60 ? 4 : 3} fill={!done && i === step ? "var(--color-brand)" : "var(--color-border)"} />
        ))}
      </svg>
      {spinning && (
        <svg viewBox={`0 0 ${size} ${size}`} className="absolute inset-0 animate-spin [animation-duration:1.6s] motion-reduce:animate-none">
          <circle
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke="var(--color-brand)"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeDasharray={`${r * 0.9} ${2 * Math.PI * r}`}
          />
        </svg>
      )}
      {done ? (
        <Check className="size-5 text-success" />
      ) : (
        <div className="text-center leading-tight">
          {size > 60 && <div className="text-[10px] text-muted-foreground">{t("flow.round")}</div>}
          <div className={cn("font-semibold text-foreground", size > 60 ? "text-sm" : "text-[11px]")}>
            {round}
            <span className="text-muted-foreground">/{max || "?"}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function HubNode({ data }: NodeProps<Node<HubData & { label: string }>>) {
  return (
    <div className="grid justify-items-center gap-1">
      <Ring {...data} />
      <div className="text-[11px] text-muted-foreground">{data.label}</div>
    </div>
  );
}

function FrameNode({ data, width, height }: NodeProps<Node<{ label: string }>>) {
  return (
    <div className="relative rounded-2xl border border-dashed border-border bg-muted/25" style={{ width, height }}>
      <span className="absolute bottom-2 left-3 text-[11px] text-muted-foreground">{data.label}</span>
    </div>
  );
}

/** A Deep-level section: its title, its ring, what it has found. */
type LaneData = { title: string; hub: HubData; label: string; sources: number; active: boolean };

function LaneNode({ data }: NodeProps<Node<LaneData>>) {
  const { t } = useT();
  return (
    <div
      className={cn(
        "flex w-[280px] cursor-pointer items-center gap-3 rounded-xl border bg-card px-3 py-2 text-xs shadow-xs transition-[border-color,box-shadow] hover:border-brand/40",
        data.active && "border-brand/60 ring-4 ring-brand/10",
      )}
    >
      <Handle type="target" position={Position.Left} id="in" className="!border-0 !bg-transparent" />
      <Handle type="source" position={Position.Right} id="out" className="!border-0 !bg-transparent" />
      <Ring {...data.hub} size={48} />
      <div className="min-w-0 flex-1">
        <div className="line-clamp-2 font-medium text-foreground">{data.title}</div>
        <div className="truncate text-[11px] text-muted-foreground">
          {data.label}
          {data.sources > 0 && ` · ${t("flow.sources", { n: data.sources })}`}
        </div>
      </div>
    </div>
  );
}

type EdgeData = { active?: boolean; travel?: number; label?: string };

/** An edge, lit and flowing while the work travels it, with dots riding along when it carries searches. */
function FlowEdge(props: EdgeProps<Edge<EdgeData>>) {
  const [path, labelX, labelY] = getSmoothStepPath({ ...props, borderRadius: 18, offset: 28 });
  const active = !!props.data?.active;
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        className={active ? "lit-flow-edge" : undefined}
        style={{ stroke: active ? "var(--color-brand)" : "var(--color-border)", strokeWidth: active ? 1.75 : 1.25 }}
      />
      {active &&
        Array.from({ length: props.data?.travel ?? 0 }, (_, i) => (
          <circle key={i} r={4} fill="var(--color-brand)" className="motion-reduce:hidden">
            <animateMotion dur="1.8s" begin={`${i * 0.6}s`} repeatCount="indefinite" path={path} />
          </circle>
        ))}
      {props.data?.label && (
        <EdgeLabelRenderer>
          <div
            className={cn(
              "pointer-events-none absolute rounded-full border bg-background px-2 py-0.5 text-[10px]",
              active ? "border-brand/40 text-brand" : "text-muted-foreground",
            )}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {props.data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const NODE_TYPES = { step: StepNode, hub: HubNode, frame: FrameNode, lane: LaneNode };
const EDGE_TYPES = { flow: FlowEdge };

type T = (key: Key, vars?: Record<string, string | number>) => string;

function edge(id: string, source: string, target: string, data: EdgeData, handles?: [string, string]): Edge<EdgeData> {
  return {
    id, source, target, type: "flow", data,
    sourceHandle: handles?.[0] ?? "out", targetHandle: handles?.[1] ?? "in",
  };
}

/** One lane's loop, laid out as the README draws it. */
function loopGraph(l: Lane, topic: string, live: boolean, t: T) {
  const cur = l.rounds[l.rounds.length - 1];
  const prev = l.rounds[l.rounds.length - 2];
  const step = STEPS.indexOf(l.phase as (typeof STEPS)[number]);
  const writing = l.writing;
  const state = (i: number): StepState => {
    if (writing) return live ? "rest" : "done";
    if (i < step) return "done";
    if (i === step) return live ? "active" : "done";
    return l.rounds.length > 1 ? "rest" : "idle";
  };
  const icons = [Brain, ScanSearch, ListChecks, Globe];
  const captions = ["Observations", "Knowledge gap agent", "Tool selector agent", "Web search · Crawler"];
  const details = [
    cur?.observed,
    cur?.complete ? t("flow.complete") : cur?.gap,
    cur?.queries.length ? t("flow.queries", { n: cur.queries.length }) : undefined,
    cur?.sources != null ? t("flow.sources", { n: cur.sources }) : undefined,
  ];
  const X = [260, 490, 720, 950];
  const nodes: Node[] = [
    { id: "frame", type: "frame", position: { x: 230, y: -40 }, width: 1080, height: 250, data: { label: t("flow.loop") }, draggable: false, selectable: false, zIndex: -1 },
    { id: "topic", type: "step", position: { x: 0, y: 40 }, draggable: false, data: { title: topic, caption: t("flow.topic"), icon: MapIcon, state: "done" } satisfies StepData },
    ...STEPS.map((s, i) => ({
      id: s, type: "step", position: { x: X[i], y: 40 }, draggable: false,
      data: {
        title: t(`flow.${s}` as Key), caption: captions[i], icon: icons[i], state: state(i), detail: details[i],
        urls: i === 3 ? cur?.urls : undefined,
      } satisfies StepData,
    })),
    {
      id: "hub", type: "hub", position: { x: 1190, y: 22 }, draggable: false, selectable: false,
      data: {
        round: cur?.round ?? 0, max: l.max, step: Math.max(step, 0), spinning: live && !writing, done: !live || writing,
        label: writing ? t("flow.write") : step >= 0 ? t(`flow.${STEPS[step]}` as Key) : "",
      },
    },
    {
      id: "writer", type: "step", position: { x: 1360, y: 40 }, draggable: false,
      data: { title: t("flow.write"), caption: "Writer agent", icon: PenLine, state: writing ? (live ? "active" : "done") : "idle" } satisfies StepData,
    },
  ];
  const edges = [
    edge("topic>observe", "topic", "observe", { active: live && step === 0 && (cur?.round ?? 1) === 1 }),
    edge("observe>gap", "observe", "gap", { active: live && step === 1 }),
    edge("gap>select", "gap", "select", { active: live && step === 2 }),
    edge("select>search", "select", "search", {
      active: live && step === 3, travel: Math.min(cur?.queries.length ?? 0, 3),
      label: cur?.queries.length ? t("flow.queries", { n: cur.queries.length }) : undefined,
    }),
    edge("search>observe", "search", "observe", {
      active: live && step === 0 && (cur?.round ?? 1) > 1,
      label: prev?.sources != null && !writing ? t("flow.sources", { n: prev.sources }) : undefined,
    }, ["down", "back"]),
    edge("gap>writer", "gap", "writer", {
      active: live && writing,
      label: writing ? (cur?.complete ? t("flow.complete") : t("flow.stopped")) : undefined,
    }, ["exit", "enter"]),
  ];
  return { nodes, edges };
}

/** The Deep level: plan, sections side by side, then one report. */
function deepGraph(m: Model, topic: string, live: boolean, t: T) {
  const planned = m.sections.length > 0;
  const rows = m.sections.length || 1;
  const mid = ((rows - 1) * 110) / 2;
  const nodes: Node[] = [
    { id: "topic", type: "step", position: { x: 0, y: mid }, draggable: false, data: { title: topic, caption: t("flow.topic"), icon: MapIcon, state: "done" } satisfies StepData },
    {
      id: "plan", type: "step", position: { x: 260, y: mid }, draggable: false,
      data: { title: t("flow.plan"), caption: "Planner agent", icon: Network, state: planned ? "done" : live ? "active" : "idle" } satisfies StepData,
    },
    {
      id: "compose", type: "step", position: { x: 880, y: mid }, draggable: false,
      data: { title: t("flow.compose"), caption: "Long writer agent", icon: PenLine, state: m.composing ? (live ? "active" : "done") : "idle" } satisfies StepData,
    },
  ];
  const edges: Edge<EdgeData>[] = [edge("topic>plan", "topic", "plan", { active: live && !planned })];
  m.sections.forEach((s, i) => {
    const l = m.lanes[s.id];
    const cur = l?.rounds[l.rounds.length - 1];
    const step = STEPS.indexOf(l?.phase as (typeof STEPS)[number]);
    const working = live && !!l && !l.writing && !m.composing;
    nodes.push({
      id: s.id, type: "lane", position: { x: 520, y: i * 110 - 6 }, draggable: false,
      data: {
        title: s.title, active: working,
        hub: { round: cur?.round ?? 0, max: l?.max ?? 0, step: Math.max(step, 0), spinning: working, done: !!l?.writing || !live },
        label: !l ? "…" : l.writing ? t("flow.write") : step >= 0 ? t(`flow.${STEPS[step]}` as Key) : "…",
        sources: l?.rounds.reduce((a, r) => a + (r.sources ?? 0), 0) ?? 0,
      } satisfies LaneData,
    });
    edges.push(edge(`plan>${s.id}`, "plan", s.id, { active: working }));
    edges.push(edge(`${s.id}>compose`, s.id, "compose", { active: live && m.composing }));
  });
  return { nodes, edges };
}

// --- the canvas --------------------------------------------------------------------------------

export function AgentFlowCanvas({ runId, topic, live }: { runId: string; topic: string; live: boolean }) {
  const { t } = useT();
  const { resolvedTheme } = useTheme();
  const [notes, setNotes] = useState(() => new Map<number, FlowNote>());
  const after = useRef(0);
  const take = (events: Schemas["EventOut"][]) => {
    const flow = events.filter((e) => e.type === "note" && e.data.kind === "flow");
    if (!flow.length) return;
    setNotes((prev) => {
      const next = new Map(prev);
      for (const e of flow) next.set(e.id, e.data as unknown as FlowNote);
      return next;
    });
  };

  // Every note so far, page by page; while the Run works, the rest as they come.
  const loaded = useQuery({
    queryKey: ["agent-flow", runId],
    queryFn: async () => {
      const all: Schemas["EventOut"][] = [];
      for (;;) {
        const r = await call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId }, query: { after: after.current } } }));
        if (!r.events.length) break;
        after.current = r.events[r.events.length - 1].id;
        all.push(...r.events);
        if (r.events.length < 500) break;
      }
      return all;
    },
  });
  useEffect(() => take(loaded.data ?? []), [loaded.data]); // eslint-disable-line react-hooks/exhaustive-deps
  useRunLive(runId, live, (d) => take(d.events));

  const model = useMemo(() => fold([...notes.entries()].sort((a, b) => a[0] - b[0]).map(([, n]) => n)), [notes]);
  const deep = model.sections.length > 0;
  const [laneId, setLaneId] = useState<string | null>(null);
  const lane = deep ? (laneId ? model.lanes[laneId] : undefined) : model.lanes.main;
  const graph = useMemo(
    () => (lane ? loopGraph(lane, laneId ? (lane.title ?? topic) : topic, live && !model.composing, t) : deepGraph(model, topic, live, t)),
    [lane, laneId, model, topic, live, t],
  );

  const [picked, setPicked] = useState<number | null>(null);
  const rounds = lane?.rounds ?? [];
  const shown = rounds.find((r) => r.round === picked) ?? rounds[rounds.length - 1];

  // The camera follows the work: the step at work and its neighbours, until the reader moves it.
  const focus = useMemo(() => {
    if (!lane || !live || model.composing) return null;
    if (lane.writing) return ["gap", "hub", "writer"];
    const i = STEPS.indexOf(lane.phase as (typeof STEPS)[number]);
    if (i < 0) return null;
    const ids: string[] = [STEPS[Math.max(0, i - 1)], STEPS[i], STEPS[Math.min(3, i + 1)]];
    if (i === 0) ids.unshift(lane.rounds.length > 1 ? "search" : "topic");
    if (i === 3) ids.push("hub");
    return ids;
  }, [lane, live, model.composing]);
  const flow = useRef<ReactFlowInstance<Node, Edge> | null>(null);
  const moved = useRef(false);
  useEffect(() => {
    moved.current = false;
  }, [laneId]);
  useEffect(() => {
    if (moved.current) return;
    setTimeout(
      () =>
        flow.current?.fitView(
          focus
            ? { nodes: focus.map((id) => ({ id })), maxZoom: 1, padding: 0.15, duration: 600 }
            : { maxZoom: 1.1, padding: 0.12, duration: 300 },
        ),
      30,
    );
  }, [focus?.join(), laneId, deep, graph.nodes.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!notes.size)
    return <p className="text-xs text-muted-foreground">{live || loaded.isLoading ? t("flow.waiting") : t("flow.none")}</p>;
  return (
    <div className="grid gap-2">
      {deep && laneId && (
        <button
          type="button"
          onClick={() => (setLaneId(null), setPicked(null))}
          className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" />
          {t("flow.overview")}
        </button>
      )}
      <div className="h-72 overflow-hidden rounded-xl border bg-background md:h-80">
        <ReactFlow
          nodes={graph.nodes}
          edges={graph.edges}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          colorMode={resolvedTheme === "dark" ? "dark" : "light"}
          onInit={(instance) => {
            flow.current = instance;
            instance.fitView({ maxZoom: 1.1, padding: 0.12 });
          }}
          onMoveStart={(e) => {
            if (e) moved.current = true;
          }}
          minZoom={0.25}
          nodesConnectable={false}
          onNodeClick={(_, n) => {
            if (n.type === "lane") (setLaneId(n.id), setPicked(null));
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {rounds.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {rounds.map((r) => (
            <button
              key={r.round}
              type="button"
              onClick={() => setPicked(r.round)}
              className={cn(
                "max-w-72 truncate rounded-full border px-2.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground",
                shown?.round === r.round && "border-brand/40 text-brand",
              )}
            >
              {t("flow.roundN", { n: r.round })}
              {r.gap && ` · ${r.gap}`}
              {r.sources != null && ` · ${t("flow.sources", { n: r.sources })}`}
            </button>
          ))}
        </div>
      )}
      {shown && (
        <div className="grid gap-2 rounded-lg border bg-muted/40 p-3 text-xs">
          {shown.observed && <Detail label={t("flow.thought")}>{shown.observed}</Detail>}
          {(shown.gap || shown.complete) && (
            <Detail label={t("flow.gapText")}>{shown.complete ? t("flow.complete") : shown.gap}</Detail>
          )}
          {shown.queries.length > 0 && (
            <Detail label={t("flow.searches")}>
              <ul className="grid gap-0.5">
                {shown.queries.map((q, i) => (
                  <li key={i} className="flex gap-1.5">
                    {q.agent === "crawl" ? <Globe className="mt-0.5 size-3 shrink-0" /> : <ScanSearch className="mt-0.5 size-3 shrink-0" />}
                    <span>
                      {q.query}
                      {q.site && <span className="text-muted-foreground"> · {q.site}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </Detail>
          )}
          {shown.urls.length > 0 && (
            <Detail label={t("flow.found")}>
              <div className="flex flex-wrap gap-1.5">
                {shown.urls.map((u) => (
                  <a
                    key={u}
                    href={u}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex max-w-56 items-center gap-1 truncate rounded-full bg-background px-2 py-0.5 hover:text-brand"
                  >
                    <Favicon url={u} className="size-3.5" />
                    {domainOf(u)}
                  </a>
                ))}
              </div>
            </Detail>
          )}
          <p className="text-[10px] text-muted-foreground">{t("flow.englishNote")}</p>
        </div>
      )}
    </div>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5">
      <div className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">{label}</div>
      <div className="text-foreground">{children}</div>
    </div>
  );
}

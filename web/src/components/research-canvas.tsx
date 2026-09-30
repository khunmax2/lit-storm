// The research tree of a Deep Research Run, as the Deep Research app draws
// it on its canvas (lit_deep-research-web, SearchFlow.vue): the topic, the
// queries it branched into, and the queries each of those led to, each with
// what it is doing now. Rebuilt from the Run's "tree" notes, so it grows
// while the Run works and is still there when it is done.
import "@xyflow/react/dist/style.css";

import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import {
  BookOpen,
  Brain,
  CircleCheckBig,
  ClipboardList,
  Clock3,
  FileSearch,
  Network,
  OctagonX,
  Search,
  SearchCheck,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";

import { api, call } from "@/api/client";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

type TreeNode = {
  id: string;
  parent?: string;
  status: string;
  query?: string;
  goal?: string;
  sources?: number;
  learnings?: number;
  message?: string;
};

const LOOK: Record<string, { icon: typeof Search; tone: string; busy?: boolean }> = {
  generating_query: { icon: ClipboardList, tone: "border-brand/40 text-brand", busy: true },
  generated_query: { icon: Clock3, tone: "border-border text-muted-foreground" },
  searching: { icon: Search, tone: "border-brand/40 text-brand", busy: true },
  search_complete: { icon: SearchCheck, tone: "border-brand/40 text-brand" },
  reading_source: { icon: BookOpen, tone: "border-brand/40 text-brand", busy: true },
  processing_search_result: { icon: Brain, tone: "border-brand/40 text-brand", busy: true },
  node_complete: { icon: CircleCheckBig, tone: "border-success/40 text-success" },
  no_evidence: { icon: FileSearch, tone: "border-border text-muted-foreground" },
  error: { icon: OctagonX, tone: "border-destructive/40 text-destructive" },
  root: { icon: Network, tone: "border-foreground/30 text-foreground" },
};

type Data = { label: string; status: string; selected: boolean };

function QueryNode({ data }: NodeProps<Node<Data>>) {
  const look = LOOK[data.status] ?? LOOK.generated_query;
  const Icon = look.icon;
  return (
    <div
      className={cn(
        "flex max-w-72 items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-xs shadow-xs",
        look.tone,
        look.busy && "animate-pulse",
        data.selected && "ring-2 ring-brand/40",
      )}
    >
      <Handle type="target" position={Position.Left} className="!border-0 !bg-transparent" />
      <Icon className="size-3.5 shrink-0" />
      <span className="truncate text-foreground">{data.label}</span>
      <Handle type="source" position={Position.Right} className="!border-0 !bg-transparent" />
    </div>
  );
}

const TYPES = { query: QueryNode };
const COLUMN = 300;
const ROW = 52;

/** Left to right: a column per level, leaves one under another, each parent
 *  level with the middle of its children. */
function layout(tree: Map<string, TreeNode>, rootLabel: string, selected: string | null) {
  // A node's parent is named when it appears, and is in its id ("0-1-2" is
  // under "0-1"). The top node, "0", is the topic itself.
  const children = new Map<string, string[]>();
  const top = new Set<string>();
  for (const n of tree.values()) {
    const parent = n.parent ?? (n.id.includes("-") ? n.id.split("-").slice(0, -1).join("-") : null);
    if (parent === null) {
      top.add(n.id);
      continue;
    }
    if (!tree.has(parent)) top.add(parent);
    const list = children.get(parent) ?? [];
    list.push(n.id);
    children.set(parent, list);
  }
  const nodes: Node<Data>[] = [];
  const edges: Edge[] = [];
  let row = 0;
  const place = (id: string, depth: number): number => {
    const kids = (children.get(id) ?? []).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    const ys = kids.map((k) => place(k, depth + 1));
    const y = ys.length ? (ys[0] + ys[ys.length - 1]) / 2 : row++ * ROW;
    const n = tree.get(id);
    nodes.push({
      id,
      type: "query",
      position: { x: depth * COLUMN, y },
      data: {
        label: n?.query || n?.goal || (top.has(id) ? rootLabel : "…"),
        status: top.has(id) ? "root" : (n?.status ?? "root"),
        selected: selected === id,
      },
      draggable: false,
    });
    for (const k of kids) {
      const busy = LOOK[tree.get(k)?.status ?? ""]?.busy;
      edges.push({ id: `${id}>${k}`, source: id, target: k, animated: !!busy });
    }
    return y;
  };
  for (const id of top) place(id, 0);
  return { nodes, edges };
}

export function ResearchCanvas({ runId, topic, live }: { runId: string; topic: string; live: boolean }) {
  const { t } = useT();
  const { resolvedTheme } = useTheme();
  const [tree, setTree] = useState(() => new Map<string, TreeNode>());
  const after = useRef(0);
  const [selected, setSelected] = useState<string | null>(null);

  // Every "tree" note since the last one read, page by page.
  const events = useQuery({
    queryKey: ["research-tree", runId],
    queryFn: async () => {
      const found: TreeNode[] = [];
      for (;;) {
        const r = await call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId }, query: { after: after.current } } }));
        if (!r.events.length) break;
        after.current = r.events[r.events.length - 1].id;
        for (const e of r.events) if (e.type === "note" && e.data.kind === "tree") found.push(e.data as unknown as TreeNode);
        if (r.events.length < 500) break;
      }
      return found;
    },
    refetchInterval: live ? 2500 : false,
  });
  useEffect(() => {
    if (!events.data?.length) return;
    setTree((prev) => {
      const next = new Map(prev);
      for (const n of events.data) next.set(n.id, { ...next.get(n.id), ...n });
      return next;
    });
  }, [events.data]);

  const graph = useMemo(() => layout(tree, topic, selected), [tree, topic, selected]);
  // Keep the whole tree in view as it grows (until the owner moves it).
  const flow = useRef<ReactFlowInstance<Node<Data>, Edge> | null>(null);
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current) setTimeout(() => flow.current?.fitView({ maxZoom: 1.3, padding: 0.15 }), 30);
  }, [graph.nodes.length]);
  const chosen = selected ? tree.get(selected) : undefined;

  if (!tree.size)
    return <p className="text-xs text-muted-foreground">{live ? t("canvas.waiting") : t("canvas.none")}</p>;
  return (
    <div className="grid gap-2">
      <div className="h-72 overflow-hidden rounded-xl border bg-background md:h-96">
        <ReactFlow
          nodes={graph.nodes}
          edges={graph.edges}
          nodeTypes={TYPES}
          colorMode={resolvedTheme === "dark" ? "dark" : "light"}
          onInit={(instance) => {
            flow.current = instance;
            instance.fitView({ maxZoom: 1.3, padding: 0.15 });
          }}
          onMoveStart={(e) => {
            if (e) moved.current = true;
          }}
          minZoom={0.3}
          nodesConnectable={false}
          onNodeClick={(_, n) => setSelected(n.id === selected ? null : n.id)}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {chosen && (
        <div className="grid gap-1 rounded-lg border bg-muted/40 p-3 text-xs">
          <div className="font-medium text-foreground">{chosen.query}</div>
          {chosen.goal && <div className="text-muted-foreground">{chosen.goal}</div>}
          <div className="flex flex-wrap gap-x-3 text-muted-foreground">
            <span>{t(`canvas.status.${chosen.status}` as Key)}</span>
            {chosen.sources != null && <span>{t("canvas.sources", { n: chosen.sources })}</span>}
            {chosen.learnings != null && <span>{t("canvas.learnings", { n: chosen.learnings })}</span>}
          </div>
          {chosen.message && <div className="text-destructive">{chosen.message}</div>}
        </div>
      )}
    </div>
  );
}

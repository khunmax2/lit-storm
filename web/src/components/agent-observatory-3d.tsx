// The agents of a STORM Run, or the table of a Co-STORM Discussion, as a 3D scene in the manner of
// AI Agent Observatory (github.com/sakshigupta372/AI-Agent-observatory): glowing cores that are
// spawned as the work goes, arcs between them, packets of information travelling along the arcs,
// the Sources read circling the search hub. Drawn from the Run's own events and the Discussion's
// own view (docs/adr/0012); nothing here is made up. Loaded only when someone opens it (React.lazy),
// so three.js does not weigh on the rest of the app.
import { Line, OrbitControls, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useQuery } from "@tanstack/react-query";
import { Pause, Play, RotateCcw } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { api, call } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useRunLive } from "@/hooks/use-run-live";
import { useT, type Key } from "@/i18n";

type Vec = [number, number, number];
type Kind = "lead" | "persona" | "expert" | "web" | "write" | "report" | "kb" | "speaker" | "you";
type Status = "idle" | "active" | "done" | "fail";
type Core = { id: string; label: string; sub?: string; kind: Kind; pos: Vec; status: Status; size?: number };
type Link = { id: string; from: string; to: string };
type Packet = { id: number; from: Vec; to: Vec; color: string; ms: number };
type Sat = { id: string; label: string; hub: string };
type Star = { id: string; label: string; pos: Vec; parent?: string; size: number };
type Ev = { id: number; at?: string | null; type: string; data: Record<string, unknown> };

const COLOR: Record<Kind, string> = {
  lead: "#22e4ff",
  persona: "#ffb547",
  expert: "#a084ff",
  web: "#7dff6a",
  write: "#ff3df2",
  report: "#ffffff",
  kb: "#22e4ff",
  speaker: "#ffb547",
  you: "#7dff6a",
};
const FINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
const clip = (s: unknown, n: number) => {
  const x = String(s ?? "").replace(/\s+/g, " ").trim();
  return x.length > n ? x.slice(0, n - 1) + "…" : x;
};
const host = (u: string) => {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return clip(u, 30);
  }
};

// ------------------------------------------------------------------ the scene's state, driven by steps

type World = {
  cores: Map<string, Core>;
  links: Map<string, Link>;
  sats: Sat[];
  stars: Star[];
  bubble: { who: string; text: string } | null;
  log: string[];
  counts: { agents: number; pages: number; tokens: number; turns: number; total: number };
};
const empty = (): World => ({
  cores: new Map(),
  links: new Map(),
  sats: [],
  stars: [],
  bubble: null,
  log: [],
  counts: { agents: 0, pages: 0, tokens: 0, turns: 0, total: 0 },
});

/** A queue of steps, each changing the world and saying how long to wait before the next. */
function useDirector() {
  const world = useRef<World>(empty());
  const [, setVersion] = useState(0);
  const [packets, setPackets] = useState<Packet[]>([]);
  const queue = useRef<(() => number)[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const paused = useRef(false);
  const seq = useRef(0);

  const tick = useCallback(() => {
    timer.current = undefined;
    if (paused.current) return;
    const step = queue.current.shift();
    if (!step) return;
    const wait = step();
    setVersion((v) => v + 1);
    timer.current = setTimeout(tick, wait);
  }, []);
  const push = useCallback(
    (...steps: (() => number)[]) => {
      queue.current.push(...steps);
      if (!timer.current && !paused.current) timer.current = setTimeout(tick, 0);
    },
    [tick],
  );
  const send = useCallback((from: string, to: string, color: string, ms = 900) => {
    const a = world.current.cores.get(from)?.pos;
    const b = world.current.cores.get(to)?.pos;
    if (!a || !b) return;
    seq.current += 1;
    const p = { id: seq.current, from: a, to: b, color, ms };
    setPackets((all) => [...all.slice(-40), p]);
  }, []);
  const arrive = useCallback((id: number) => setPackets((all) => all.filter((p) => p.id !== id)), []);
  const reset = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = undefined;
    queue.current = [];
    world.current = empty();
    setPackets([]);
    setVersion((v) => v + 1);
  }, []);
  const pause = useCallback(
    (on: boolean) => {
      paused.current = on;
      if (!on && !timer.current) timer.current = setTimeout(tick, 0);
      setVersion((v) => v + 1);
    },
    [tick],
  );
  useEffect(() => () => clearTimeout(timer.current), []);
  return { world, packets, push, send, arrive, reset, pause, paused };
}

function core(w: World, c: Omit<Core, "status"> & { status?: Status }) {
  const had = w.cores.get(c.id);
  if (had) {
    Object.assign(had, c);
    return had;
  }
  const made = { status: "active" as Status, ...c };
  w.cores.set(c.id, made);
  if (c.kind !== "lead" && c.kind !== "kb" && c.kind !== "web" && c.kind !== "you") w.counts.agents += 1;
  return made;
}
const link = (w: World, from: string, to: string) => w.links.set(`${from}>${to}`, { id: `${from}>${to}`, from, to });
const say = (w: World, line: string) => {
  w.log = [...w.log.slice(-5), line];
};
const status = (w: World, id: string, s: Status) => {
  const c = w.cores.get(id);
  if (c) c.status = s;
};

// ------------------------------------------------------------------ 3D pieces

function Glow({ color, radius, strength }: { color: string; radius: number; strength: number }) {
  return (
    <mesh>
      <sphereGeometry args={[radius, 24, 24]} />
      <meshBasicMaterial color={color} transparent opacity={strength} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

type Registry = Map<string, THREE.Object3D>;

function CoreMesh({ c, onPick, picked, registry }: { c: Core; onPick: (c: Core) => void; picked: boolean; registry: Registry }) {
  const group = useRef<THREE.Group>(null);
  useEffect(() => {
    const g = group.current;
    if (g) registry.set(c.id, g);
    return () => {
      if (registry.get(c.id) === g) registry.delete(c.id);
    };
  }, [c.id, registry]);
  const shell = useRef<THREE.Mesh>(null);
  const ring = useRef<THREE.Mesh>(null);
  const born = useRef<number | null>(null);
  const color = COLOR[c.kind];
  const r = (c.size ?? 1) * (c.kind === "lead" || c.kind === "kb" ? 0.46 : c.kind === "report" ? 0.42 : 0.32);
  const active = c.status === "active";
  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    if (born.current == null) born.current = t;
    const grow = Math.min(1, (t - born.current) / 0.7);
    const s = (1 - Math.pow(1 - grow, 3)) * (picked ? 1.2 : 1);
    group.current?.scale.setScalar(Math.max(0.001, s));
    if (group.current) group.current.position.y = c.pos[1] + Math.sin(t * 0.7 + c.pos[0]) * 0.07;
    if (shell.current) shell.current.rotation.y += delta * (active ? 0.7 : 0.15);
    if (ring.current) ring.current.rotation.z += delta * (active ? 1.5 : 0.3);
  });
  const glow = c.status === "fail" ? 0.04 : active ? 0.16 : c.status === "done" ? 0.05 : 0.03;
  const tone = c.status === "fail" ? "#ff4d6d" : color;
  return (
    <group
      ref={group}
      position={c.pos}
      onClick={(e) => {
        e.stopPropagation();
        onPick(c);
      }}
    >
      <mesh>
        <icosahedronGeometry args={[r, 1]} />
        <meshStandardMaterial color={tone} emissive={tone} emissiveIntensity={active ? 2.4 : c.status === "done" ? 0.9 : 0.4} toneMapped={false} />
      </mesh>
      <mesh ref={shell}>
        <icosahedronGeometry args={[r * 1.55, 1]} />
        <meshBasicMaterial color={tone} wireframe transparent opacity={active ? 0.8 : 0.28} toneMapped={false} />
      </mesh>
      <mesh ref={ring} rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[r * 2.1, 0.012, 8, 64]} />
        <meshBasicMaterial color={tone} transparent opacity={active ? 0.95 : 0.35} toneMapped={false} />
      </mesh>
      <Glow color={tone} radius={r * 2.3} strength={glow} />
    </group>
  );
}

function arc(a: Vec, b: Vec) {
  const va = new THREE.Vector3(...a);
  const vb = new THREE.Vector3(...b);
  const mid = va.clone().add(vb).multiplyScalar(0.5);
  mid.y += va.distanceTo(vb) * 0.22 + 0.3;
  return new THREE.QuadraticBezierCurve3(va, mid, vb);
}

function LinkLine({ a, b, on, color }: { a: Vec; b: Vec; on: boolean; color: string }) {
  const points = useMemo(() => arc(a, b).getPoints(40), [a, b]);
  return <Line points={points} color={color} lineWidth={on ? 1.8 : 1} transparent opacity={on ? 0.75 : 0.18} />;
}

function PacketMesh({ p, onDone }: { p: Packet; onDone: (id: number) => void }) {
  const mesh = useRef<THREE.Group>(null);
  const curve = useMemo(() => arc(p.from, p.to), [p.from, p.to]);
  const start = useRef<number | null>(null);
  const done = useRef(false);
  useFrame((state) => {
    if (done.current) return;
    const now = state.clock.elapsedTime * 1000;
    if (start.current == null) start.current = now;
    const t = Math.min(1, (now - start.current) / p.ms);
    mesh.current?.position.copy(curve.getPoint(t));
    if (t >= 1) {
      done.current = true;
      onDone(p.id);
    }
  });
  return (
    <group ref={mesh} position={p.from}>
      <mesh>
        <sphereGeometry args={[0.07, 12, 12]} />
        <meshBasicMaterial color={p.color} toneMapped={false} />
      </mesh>
      <Glow color={p.color} radius={0.22} strength={0.35} />
    </group>
  );
}

function Satellites({ sats, hub }: { sats: Sat[]; hub: Vec }) {
  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.18;
  });
  return (
    <group ref={group} position={hub}>
      {sats.map((s, i) => {
        const ring = 0.9 + (i % 3) * 0.35;
        const a = i * 2.399;
        const y = ((i * 37) % 11) / 11 - 0.5;
        return (
          <mesh key={s.id} position={[Math.cos(a) * ring, y * 0.9, Math.sin(a) * ring]}>
            <octahedronGeometry args={[0.06, 0]} />
            <meshBasicMaterial color="#7dff6a" toneMapped={false} />
          </mesh>
        );
      })}
    </group>
  );
}

function MindStars({ stars }: { stars: Star[] }) {
  const byId = useMemo(() => new Map(stars.map((s) => [s.id, s])), [stars]);
  return (
    <group>
      {stars.map((s) => (
        <group key={s.id}>
          <mesh position={s.pos}>
            <sphereGeometry args={[0.05 + Math.min(0.12, s.size * 0.012), 10, 10]} />
            <meshBasicMaterial color="#cfe8ff" toneMapped={false} />
          </mesh>
          {s.parent && byId.get(s.parent) && (
            <Line points={[byId.get(s.parent)!.pos, s.pos]} color="#22e4ff" lineWidth={0.6} transparent opacity={0.25} />
          )}
        </group>
      ))}
    </group>
  );
}

/** Keeps each core's label (a DOM element over the canvas) on its core: projected every frame,
 *  hidden while the core is behind the camera. */
function LabelSync({ registry, labels }: { registry: Registry; labels: Map<string, HTMLDivElement> }) {
  const v = useMemo(() => new THREE.Vector3(), []);
  useFrame(({ camera, size }) => {
    labels.forEach((el, id) => {
      const obj = registry.get(id);
      if (!obj) {
        el.style.display = "none";
        return;
      }
      obj.getWorldPosition(v);
      v.y += Number(el.dataset.lift || 0.9) * obj.scale.y;
      v.project(camera);
      if (v.z > 1 || obj.scale.y < 0.2) {
        el.style.display = "none";
        return;
      }
      el.style.display = "";
      el.style.transform = `translate3d(${((v.x + 1) / 2) * size.width}px, ${((1 - v.y) / 2) * size.height}px, 0) translate(-50%, -100%)`;
      el.style.zIndex = String(Math.round((1 - v.z) * 1000));
    });
  });
  return null;
}

function Scene({ world, packets, onArrive, picked, onPick, registry, labels, target }: {
  target: Vec;
  world: World;
  packets: Packet[];
  onArrive: (id: number) => void;
  picked: string | null;
  onPick: (c: Core) => void;
  registry: Registry;
  labels: Map<string, HTMLDivElement>;
}) {
  const cores = [...world.cores.values()];
  const hub = world.cores.get("web")?.pos;
  return (
    <>
      <ambientLight intensity={0.4} />
      <Stars radius={70} depth={40} count={1800} factor={3} fade speed={0.6} />
      {[...world.links.values()].map((l) => {
        const a = world.cores.get(l.from);
        const b = world.cores.get(l.to);
        if (!a || !b) return null;
        return <LinkLine key={l.id} a={a.pos} b={b.pos} on={b.status === "active"} color={COLOR[b.kind]} />;
      })}
      {cores.map((c) => (
        <CoreMesh key={c.id} c={c} picked={picked === c.id} onPick={onPick} registry={registry} />
      ))}
      {packets.map((p) => (
        <PacketMesh key={p.id} p={p} onDone={onArrive} />
      ))}
      {hub && <Satellites sats={world.sats} hub={hub} />}
      <MindStars stars={world.stars} />
      <OrbitControls target={target} enablePan={false} enableDamping autoRotate autoRotateSpeed={0.35} minDistance={5} maxDistance={26} />
      <LabelSync registry={registry} labels={labels} />
    </>
  );
}

function webglOk() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** The frame both scenes share: the canvas, the HUD over it, and replay controls. */
function Stage({
  title,
  director,
  hud,
  onReplay,
  canReplay,
  camera = [0, 2.5, 14],
  target = [0, 0, 0],
}: {
  camera?: Vec;
  target?: Vec;
  title: string;
  director: ReturnType<typeof useDirector>;
  hud: ReactNode;
  onReplay: () => void;
  canReplay: boolean;
}) {
  const { t } = useT();
  const [picked, setPicked] = useState<Core | null>(null);
  const ok = useMemo(webglOk, []);
  const registry = useMemo<Registry>(() => new Map(), []);
  const labels = useMemo(() => new Map<string, HTMLDivElement>(), []);
  const w = director.world.current;
  if (!ok) return <p className="text-xs text-muted-foreground">{t("obs3d.noWebgl")}</p>;
  return (
    <div className="obs3d relative h-[26rem] overflow-hidden rounded-xl border md:h-[32rem]">
      <style>{OBS3D_CSS}</style>
      <Canvas camera={{ position: camera, fov: 50 }} dpr={[1, 2]} onPointerMissed={() => setPicked(null)}>
        <Scene world={w} packets={director.packets} onArrive={director.arrive} picked={picked?.id ?? null} onPick={setPicked} registry={registry} labels={labels} target={target} />
      </Canvas>
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {[...w.cores.values()].map((c) => {
          const tone = c.status === "fail" ? "#ff4d6d" : COLOR[c.kind];
          const r = (c.size ?? 1) * (c.kind === "lead" || c.kind === "kb" ? 0.46 : c.kind === "report" ? 0.42 : 0.32);
          return (
            <div
              key={c.id}
              ref={(el) => {
                if (el) labels.set(c.id, el);
                else labels.delete(c.id);
              }}
              data-lift={r * 2.2}
              className="obs3d-label absolute top-0 left-0"
              data-state={c.status}
              style={{ ["--c" as string]: tone, display: "none" }}
            >
              <b>{clip(c.label, 34)}</b>
              {c.sub && (c.status === "active" || picked?.id === c.id) && <span>{clip(c.sub, 46)}</span>}
            </div>
          );
        })}
      </div>
      <div className="obs3d-hud pointer-events-none absolute inset-x-3 top-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="obs3d-title">{title}</div>
          {hud}
        </div>
        <div className="pointer-events-auto flex gap-1">
          {canReplay && (
            <>
              <Button
                size="icon"
                variant="outline"
                className="size-7 border-cyan-400/40 bg-black/40 text-cyan-200"
                aria-label={director.paused.current ? t("obs3d.play") : t("obs3d.pause")}
                onClick={() => director.pause(!director.paused.current)}
              >
                {director.paused.current ? <Play /> : <Pause />}
              </Button>
              <Button size="icon" variant="outline" className="size-7 border-cyan-400/40 bg-black/40 text-cyan-200" aria-label={t("obs3d.replay")} onClick={onReplay}>
                <RotateCcw />
              </Button>
            </>
          )}
        </div>
      </div>
      {w.bubble && (
        <div className="obs3d-bubble pointer-events-none absolute inset-x-3 bottom-3 md:right-auto md:max-w-xl">
          <b>{w.bubble.who}</b>
          <span>{w.bubble.text}</span>
        </div>
      )}
      {!w.bubble && w.log.length > 0 && (
        <ol className="obs3d-log pointer-events-none absolute bottom-3 left-3 max-w-md">
          {w.log.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ol>
      )}
      {picked && (
        <div className="obs3d-pick absolute right-3 bottom-3 max-w-xs">
          <b>{picked.label}</b>
          {picked.sub && <span>{picked.sub}</span>}
        </div>
      )}
    </div>
  );
}

const OBS3D_CSS = `
.obs3d { background: radial-gradient(900px 500px at 50% 0%, #0b2242 0%, #03060c 60%); color: #d4ebff; }
.obs3d-title { font: 700 11px ui-monospace, Consolas, monospace; letter-spacing: .2em; color: #22e4ff; text-shadow: 0 0 10px rgba(34,228,255,.7); text-transform: uppercase; }
.obs3d-meters { display: flex; gap: 12px; margin-top: 4px; font: 11px ui-monospace, Consolas, monospace; color: #7591ad; flex-wrap: wrap; }
.obs3d-meters b { color: #d4ebff; font-size: 14px; margin-right: 4px; text-shadow: 0 0 8px rgba(34,228,255,.5); }
.obs3d-label { white-space: nowrap; text-align: center; font-size: 11px; line-height: 1.25; color: #d4ebff; text-shadow: 0 0 6px #000, 0 0 2px #000; }
.obs3d-label b { display: block; font-weight: 600; color: var(--c); }
.obs3d-label span { display: block; font-size: 9.5px; color: #8fa9c4; }
.obs3d-label[data-state="idle"], .obs3d-label[data-state="done"] { opacity: .75; }
.obs3d-log { list-style: none; margin: 0; padding: 0; font: 11px ui-monospace, Consolas, monospace; color: #9fc3e0; }
.obs3d-log li { padding: 1px 0; text-shadow: 0 0 4px #000; }
.obs3d-log li:last-child { color: #7dff6a; }
.obs3d-bubble, .obs3d-pick { border: 1px solid rgba(34,228,255,.35); background: rgba(3,9,18,.82); border-radius: 8px; padding: 8px 12px; font-size: 12.5px; line-height: 1.55; box-shadow: 0 0 18px rgba(34,228,255,.15); }
.obs3d-bubble b, .obs3d-pick b { display: block; color: #ffb547; font-size: 11.5px; margin-bottom: 2px; }
.obs3d-pick span { color: #9fc3e0; font-size: 11.5px; }
`;

// ------------------------------------------------------------------ STORM

const STORM_POS = {
  lead: [0, 2.6, 0] as Vec,
  expert: [0, 0, 0] as Vec,
  web: [5, 0.4, -1.2] as Vec,
  outline: [-1.2, -3, -3.4] as Vec,
  article: [1.6, -3.3, -3.8] as Vec,
  polish: [4.2, -3, -3.2] as Vec,
  report: [6, -1.6, -1.6] as Vec,
};

/** STORM's agents: perspectives that each interview a topic expert, who searches the web; then the
 *  outline, section and polishing writers in turn. From the Run's stage, usage and note events. */
export function StormObservatory3D({ runId, live }: { runId: string; live: boolean }) {
  const { t } = useT();
  const director = useDirector();
  const { push, send, world } = director;
  const turn = useRef(0);

  const events = useQuery({
    queryKey: ["observatory-3d", runId],
    queryFn: async () => {
      const all: Ev[] = [];
      let after = 0;
      for (;;) {
        const r = await call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId }, query: { after } } }));
        if (!r.events.length) return { events: all, status: r.status };
        after = r.events[r.events.length - 1].id;
        all.push(...(r.events as unknown as Ev[]));
        if (r.events.length < 500) return { events: all, status: r.status };
      }
    },
  });
  const seen = useRef(new Set<number>());

  const step = useCallback(
    (e: Ev, fast: boolean): (() => number)[] => {
      const w = () => world.current;
      const d = e.data || {};
      const gap = (ms: number) => (fast ? Math.min(ms, 40) : ms);
      if (e.type === "usage") {
        return [
          () => {
            for (const u of Object.values((d.llm || {}) as Record<string, { prompt_tokens?: number; completion_tokens?: number }>))
              w().counts.tokens += (u.prompt_tokens || 0) + (u.completion_tokens || 0);
            return 0;
          },
        ];
      }
      if (e.type === "stage") {
        const s = String(d.stage);
        return [
          () => {
            const x = w();
            say(x, `${t("obs3d.stage")}: ${t(`stage.${s}` as Key) || s}`);
            core(x, { id: "lead", label: "STORM", sub: t(`stage.${s}` as Key) || s, kind: "lead", pos: STORM_POS.lead });
            if (s === "research") {
              core(x, { id: "expert", label: t("obs3d.expert"), kind: "expert", pos: STORM_POS.expert });
              core(x, { id: "web", label: t("obs3d.web"), kind: "web", pos: STORM_POS.web });
              link(x, "expert", "web");
            }
            const chain: [string, Key, Vec, string][] = [
              ["outline", "obs3d.outline", STORM_POS.outline, "expert"],
              ["article", "obs3d.article", STORM_POS.article, "outline"],
              ["polish", "obs3d.polish", STORM_POS.polish, "article"],
              ["report", "obs3d.report", STORM_POS.report, "polish"],
            ];
            const at = { outline: 0, article: 1, polish: 2, normalize: 3 }[s];
            if (at != null) {
              x.cores.forEach((c) => {
                if (c.status === "active" && c.kind !== "lead") c.status = "done";
              });
              const [id, label, pos, from] = chain[at];
              core(x, { id, label: t(label), kind: id === "report" ? "report" : "write", pos });
              link(x, x.cores.has(from) ? from : "lead", id);
              send(x.cores.has(from) ? from : "lead", id, "#ff3df2", 1100);
            }
            return gap(900);
          },
        ];
      }
      if (e.type !== "note") return [];
      if (d.kind === "perspectives") {
        const list = (d.perspectives as string[]) || [];
        return list.map((p, i) => () => {
          const x = w();
          const [name, ...rest] = String(p).split(":");
          const a = (i / Math.max(1, list.length)) * Math.PI * 2;
          const id = `persona:${i}`;
          core(x, { id, label: clip(name, 30), sub: clip(rest.join(":"), 60), kind: "persona", pos: [-5, Math.sin(a) * 2.6, Math.cos(a) * 2.6] });
          link(x, "lead", id);
          link(x, id, "expert");
          send("lead", id, "#22e4ff", 700);
          if (i === 0) say(x, t("obs3d.perspectives", { n: list.length }));
          return gap(420);
        });
      }
      if (d.kind === "browsed") {
        const urls = ((d.urls as string[]) || []).slice(0, 12);
        return [
          () => {
            const x = w();
            const personas = [...x.cores.values()].filter((c) => c.kind === "persona");
            const who = personas.length ? personas[turn.current++ % personas.length].id : "lead";
            send(who, "expert", "#22e4ff", 800);
            x.counts.pages += ((d.urls as string[]) || []).length;
            return gap(500);
          },
          () => {
            send("expert", "web", "#a084ff", 800);
            return gap(650);
          },
          () => {
            const x = w();
            urls.forEach((u) => {
              if (!x.sats.some((s) => s.id === u)) x.sats.push({ id: u, label: host(u), hub: "web" });
            });
            x.sats = x.sats.slice(-90);
            send("web", "expert", "#7dff6a", 800);
            say(x, t("obs3d.read", { n: ((d.urls as string[]) || []).length, site: urls[0] ? host(urls[0]) : "" }));
            return gap(700);
          },
        ];
      }
      return [];
    },
    [send, t, world],
  );

  const play = useCallback(
    (evs: Ev[], final: string | null, fast = false) => {
      director.reset();
      seen.current = new Set();
      turn.current = 0;
      push(() => {
        core(world.current, { id: "lead", label: "STORM", kind: "lead", pos: STORM_POS.lead });
        return 300;
      });
      for (const e of evs) {
        seen.current.add(e.id);
        push(...step(e, fast));
      }
      if (final) push(() => settle(world.current, final, t));
    },
    [director, push, step, t, world],
  );

  useEffect(() => {
    if (events.data) play(events.data.events, FINAL.has(events.data.status) ? events.data.status : null);
    // play once per load; a replay starts it again
  }, [events.data]); // eslint-disable-line react-hooks/exhaustive-deps

  useRunLive(runId, live, (r) => {
    for (const e of r.events as unknown as Ev[]) {
      if (seen.current.has(e.id)) continue;
      seen.current.add(e.id);
      push(...step(e, false));
    }
    if (FINAL.has(r.status)) push(() => settle(world.current, r.status, t));
  });

  const c = world.current.counts;
  return (
    <Stage
      title={t("obs3d.storm")}
      director={director}
      canReplay={!live && !!events.data}
      onReplay={() => events.data && play(events.data.events, events.data.status)}
      hud={
        <div className="obs3d-meters">
          <span><b>{c.agents}</b>{t("obs3d.agents")}</span>
          <span><b>{c.pages}</b>{t("obs3d.pages")}</span>
          <span><b>{world.current.sats.length}</b>{t("obs3d.sources")}</span>
          <span><b>{c.tokens >= 1000 ? Math.round(c.tokens / 1000) + "k" : c.tokens}</b>{t("obs3d.tokens")}</span>
        </div>
      }
    />
  );
}

function settle(w: World, s: string, t: ReturnType<typeof useT>["t"]) {
  const ok = s === "succeeded";
  w.cores.forEach((c) => {
    if (c.status === "active") c.status = ok ? "done" : "fail";
  });
  status(w, "lead", ok ? "done" : "fail");
  if (ok) status(w, "report", "active");
  say(w, ok ? t("obs3d.done") : t("obs3d.failed"));
  return 0;
}

// ------------------------------------------------------------------ Co-STORM

type MindNode = { name: string; count: number; children: MindNode[] };
type ViewTurn = { role: string; role_description: string; type: string; text: string; cited: number[]; warmup: boolean };
type DiscussionView = { topic: string; turns: ViewTurn[]; mind_map: MindNode[]; sources: Record<string, { url: string; title: string }>; experts: string[] };

function speakerOf(role: string) {
  const r = role.toLowerCase();
  if (role === "Guest") return "you";
  if (r.includes("moderator")) return "moderator";
  if (r.startsWith("background discussion expert")) return "bg";
  return "expert:" + role;
}

/** A Co-STORM table: the moderator, the experts and you around it, the knowledge base (the mind map)
 *  above its middle, and the web below. Each utterance lights its speaker and sends what it found
 *  to the knowledge base; what it cited comes up from the web first. */
export function CoStormObservatory3D({ view, currentId, live }: { view: DiscussionView | null; currentId: string | null; live: boolean }) {
  const { t } = useT();
  const director = useDirector();
  const { push, send, world } = director;
  const played = useRef(0);

  const seat = useCallback((x: World, id: string, label: string, sub?: string) => {
    if (x.cores.has(id)) return id;
    core(x, { id, label, sub, kind: id === "you" ? "you" : "speaker", pos: [0, 0, 0], status: "idle" });
    link(x, id, "kb");
    // Everyone at the table, evenly round it; you sit nearest the camera.
    const seats = [...x.cores.values()].filter((c) => c.kind === "speaker" || c.kind === "you");
    const order = [...seats.filter((c) => c.kind !== "you"), ...seats.filter((c) => c.kind === "you")];
    order.forEach((c, i) => {
      const a = Math.PI / 2 + ((i + 1) / order.length) * Math.PI * 2;
      c.pos = [Math.cos(a) * 4.6, 0, Math.sin(a) * 4.6];
    });
    return id;
  }, []);

  const build = useCallback(
    (v: DiscussionView) => {
      const x = world.current;
      core(x, { id: "kb", label: t("obs3d.kb"), sub: v.topic, kind: "kb", pos: [0, 0.4, 0] });
      core(x, { id: "web", label: t("obs3d.web"), kind: "web", pos: [0, -2.8, 0], status: "idle" });
      link(x, "web", "kb");
      seat(x, "moderator", t("obs3d.moderator"));
      if (v.turns.some((u) => speakerOf(u.role) === "bg")) seat(x, "bg", t("obs3d.bgExpert"));
      v.experts.forEach((e) => seat(x, "expert:" + e, e));
      seat(x, "you", t("obs3d.you"));
      // The mind map as a constellation over the table, one star per concept.
      const stars: Star[] = [];
      let i = 0;
      const walk = (nodes: MindNode[], depth: number, parent?: string) =>
        nodes.forEach((n) => {
          const id = `${parent ?? "m"}/${i}`;
          const a = i * 2.399;
          const r = 0.7 + depth * 0.75;
          stars.push({ id, label: n.name, pos: [Math.cos(a) * r, 2 + depth * 0.55, Math.sin(a) * r], parent, size: n.count });
          i += 1;
          walk(n.children || [], depth + 1, id);
        });
      walk(v.mind_map || [], 0);
      x.stars = stars;
      x.counts.total = v.turns.length;
    },
    [seat, t, world],
  );

  const turnSteps = useCallback(
    (v: DiscussionView, k: number): (() => number)[] => {
      const turn = v.turns[k];
      const who = speakerOf(turn.role);
      const label = who === "you" ? t("obs3d.you") : who === "moderator" ? t("obs3d.moderator") : who === "bg" ? t("obs3d.bgExpert") : turn.role;
      const cited = [...new Set(turn.cited)].slice(0, 3);
      return [
        () => {
          const x = world.current;
          const id = seat(x, who, label, who === "bg" ? undefined : turn.role_description);
          x.cores.forEach((c) => {
            if ((c.kind === "speaker" || c.kind === "you") && c.status === "active") c.status = "done";
          });
          status(x, id, "active");
          x.bubble = { who: label + (turn.type ? ` · ${turn.type}` : ""), text: clip(turn.text.replace(/\[\d+\]/g, ""), 220) };
          x.counts.turns = k + 1;
          cited.forEach((n) => {
            const s = v.sources[String(n)];
            if (s && !x.sats.some((y) => y.id === s.url)) x.sats.push({ id: s.url, label: host(s.url), hub: "web" });
          });
          if (cited.length) {
            status(x, "web", "active");
            send("web", id, "#7dff6a", 900);
          }
          return cited.length ? 1000 : 300;
        },
        () => {
          status(world.current, "web", "idle");
          send(who, "kb", COLOR[who === "you" ? "you" : "speaker"], 1000);
          return 2200;
        },
      ];
    },
    [seat, send, t, world],
  );

  const play = useCallback(
    (v: DiscussionView) => {
      director.reset();
      build(v);
      for (let k = 0; k < v.turns.length; k++) push(...turnSteps(v, k));
      push(() => {
        world.current.bubble = null;
        say(world.current, t("obs3d.tableDone", { n: v.turns.length }));
        return 0;
      });
      played.current = v.turns.length;
    },
    [build, director, push, t, turnSteps, world],
  );

  useEffect(() => {
    if (!view) return;
    if (played.current === 0) play(view);
    else if (view.turns.length > played.current) {
      // A new Turn finished: rebuild the stars and play only what was said since.
      build(view);
      for (let k = played.current; k < view.turns.length; k++) push(...turnSteps(view, k));
      played.current = view.turns.length;
    }
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  // While a Turn works: what it reads goes from the web to the knowledge base.
  useRunLive(currentId ?? "", live && !!currentId, (r) => {
    for (const e of r.events as unknown as Ev[]) {
      const d = e.data || {};
      if (e.type === "note" && d.kind === "browsed") {
        push(() => {
          const x = world.current;
          ((d.urls as string[]) || []).slice(0, 8).forEach((u) => {
            if (!x.sats.some((s) => s.id === u)) x.sats.push({ id: u, label: host(u), hub: "web" });
          });
          status(x, "web", "active");
          send("web", "kb", "#7dff6a", 900);
          say(x, t("obs3d.read", { n: ((d.urls as string[]) || []).length, site: host(((d.urls as string[]) || [""])[0]) }));
          return 700;
        });
      } else if (e.type === "note" && d.kind === "warmup") {
        push(() => {
          say(world.current, clip(d.message, 90));
          return 200;
        });
      }
    }
  });

  if (!view) return <p className="text-xs text-muted-foreground">{t("obs3d.waiting")}</p>;
  const c = world.current.counts;
  return (
    <Stage
      title={t("obs3d.costorm")}
      camera={[0, 8.5, 11.5]}
      target={[0, -2.2, 0]}
      director={director}
      canReplay={!!view.turns.length}
      onReplay={() => play(view)}
      hud={
        <div className="obs3d-meters">
          <span><b>{c.turns}/{c.total}</b>{t("obs3d.turns")}</span>
          <span><b>{view.experts.length}</b>{t("obs3d.experts")}</span>
          <span><b>{world.current.stars.length}</b>{t("obs3d.concepts")}</span>
          <span><b>{world.current.sats.length}</b>{t("obs3d.sources")}</span>
        </div>
      }
    />
  );
}

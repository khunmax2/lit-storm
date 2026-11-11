// A Discussion at a glance, flat (pages/discussion.tsx): who sits at the table
// on the left, the topic in the middle, the mind map's top topics on the right.
// Picking a speaker or a topic here picks it in the side column too (one
// selection, kept by components/costorm-room's useRoom). The replay walks the
// view's utterances in order and lights whoever is speaking.
import { CheckCircle2, Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { GKP, GUEST, initial, shortRole, tone, type Room, type RoomTurn } from "@/components/costorm-room";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

export type MindNode = { name: string; count: number; children: MindNode[] };

/** A top topic's colour, the same on the map and in the mind map beside it. */
const TOPIC_TONES = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#14b8a6", "#ef4444"];
export const topicTone = (i: number) => TOPIC_TONES[i % TOPIC_TONES.length];
export const topicKey = (i: number) => `topic:${i}`;

/** The seat an utterance belongs to: the warm start's background moderator is the moderator. */
export function seatOf(role: string) {
  return role.toLowerCase().includes("moderator") ? "Moderator" : role;
}

/** How far the replay has got: every utterance shown unless the owner replays them. */
export function useReplay(total: number) {
  const [shown, setShown] = useState(total);
  const [playing, setPlaying] = useState(false);
  const seen = useRef(total);
  // New utterances arrive while the owner watches the end: they show at once.
  useEffect(() => {
    const before = seen.current;
    seen.current = total;
    setShown((s) => (s >= before ? total : s));
  }, [total]);
  useEffect(() => {
    if (!playing) return;
    if (shown >= total) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setShown((s) => s + 1), 1100);
    return () => clearTimeout(timer);
  }, [playing, shown, total]);
  return {
    shown,
    total,
    playing,
    play: () => {
      if (shown >= total) setShown(0);
      setPlaying(true);
    },
    pause: () => setPlaying(false),
    first: () => {
      setPlaying(false);
      setShown(0);
    },
    last: () => {
      setPlaying(false);
      setShown(total);
    },
  };
}
export type Replay = ReturnType<typeof useReplay>;

const ROW = 50;
const W = 680;
const CX = W / 2;

export function CoStormMap2D({
  room,
  topic,
  topics,
  turns,
  replay,
}: {
  room: Room;
  topic: string;
  topics: MindNode[];
  turns: RoomTurn[];
  replay: Replay;
}) {
  const { t } = useT();
  const speakers = room.seats;
  const rows = Math.max(speakers.length, topics.length, 3);
  const H = rows * ROW + 20;
  const CY = H / 2;
  const yAt = (n: number, i: number) => (H - n * ROW) / 2 + ROW / 2 + i * ROW;
  const speaking = replay.playing || replay.shown < replay.total ? turns[replay.shown - 1] : undefined;
  const active = speaking ? seatOf(speaking.role) : null;
  const picked = room.picked;
  const lit = (key: string) => (picked ? picked === key : !active || active === key);
  const label = (role: string, name: string) =>
    role === "Moderator" || role === GKP || role === GUEST ? name : shortRole(name);

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <div className="relative mx-auto" style={{ width: W, height: H }}>
          <svg aria-hidden width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="absolute inset-0">
            <g fill="none" strokeWidth={2} strokeLinecap="round">
              {speakers.map((s, i) => {
                const y = yAt(speakers.length, i);
                return (
                  <path
                    key={s.role}
                    d={`M226 ${y} C 262 ${y}, 262 ${CY}, ${CX - 48} ${CY}`}
                    stroke={tone(s.role)}
                    strokeOpacity={lit(s.role) ? (active === s.role ? 0.95 : 0.6) : 0.15}
                    strokeWidth={active === s.role ? 3 : 2}
                    className="transition-[stroke-opacity]"
                  />
                );
              })}
              {topics.map((n, i) => {
                const y = yAt(topics.length, i);
                return (
                  <path
                    key={`${n.name}-${i}`}
                    d={`M${CX + 48} ${CY} C ${CX + 80} ${CY}, ${CX + 80} ${y}, 452 ${y}`}
                    stroke={topicTone(i)}
                    strokeOpacity={lit(topicKey(i)) ? 0.65 : 0.15}
                    className="transition-[stroke-opacity]"
                  />
                );
              })}
            </g>
          </svg>

          {speakers.map((s, i) => {
            const key = s.role;
            const on = picked === key || active === key;
            return (
              <button
                key={key}
                type="button"
                aria-pressed={picked === key}
                title={s.name}
                onClick={() => room.pick(key)}
                className={cn(
                  "absolute flex h-8 max-w-[210px] items-center gap-2 rounded-full border bg-card py-0 pr-3 pl-1 text-[13px] font-medium shadow-xs transition-[opacity,box-shadow]",
                  on && "border-brand ring-3 ring-brand/20",
                  !lit(key) && "opacity-40",
                )}
                style={{ right: W - 226, top: yAt(speakers.length, i) - 16, borderColor: on ? undefined : `${tone(key)}55` }}
              >
                <span
                  aria-hidden
                  className="flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white"
                  style={{ background: tone(key) }}
                >
                  {initial(s.name)}
                </span>
                <span className="truncate">{label(s.role, s.name)}</span>
              </button>
            );
          })}

          <div
            className="absolute flex items-center justify-center rounded-full border-2 border-brand/25 bg-card p-2 text-center font-semibold text-brand shadow-[0_0_0_8px_color-mix(in_oklab,var(--brand)_8%,transparent),0_6px_18px_rgb(30_58_138/0.12)]"
            style={{ left: CX - 48, top: CY - 48, width: 96, height: 96 }}
            title={topic}
          >
            <span className={cn("line-clamp-3 leading-tight", topic.length <= 8 ? "text-2xl" : "text-xs")}>{topic}</span>
          </div>

          {topics.map((n, i) => {
            const key = topicKey(i);
            return (
              <button
                key={`${n.name}-${i}`}
                type="button"
                aria-pressed={picked === key}
                title={n.name}
                onClick={() => room.pick(key)}
                className={cn(
                  "absolute flex h-8 max-w-[220px] items-center gap-2 rounded-full border py-0 pr-3.5 pl-1.5 text-[13px] font-semibold transition-[opacity,box-shadow]",
                  picked === key && "border-brand ring-3 ring-brand/20",
                  !lit(key) && "opacity-40",
                )}
                style={{
                  left: 450,
                  top: yAt(topics.length, i) - 16,
                  background: `color-mix(in oklab, ${topicTone(i)} 10%, var(--card))`,
                  borderColor: picked === key ? undefined : `${topicTone(i)}66`,
                }}
              >
                <span aria-hidden className="size-3 shrink-0 rounded-full" style={{ background: topicTone(i) }} />
                <span className="truncate">{n.name}</span>
              </button>
            );
          })}
        </div>
      </div>
      {speaking ? (
        <p className="mx-auto line-clamp-2 max-w-xl text-center text-xs text-muted-foreground" aria-live="polite">
          <span className="font-medium text-foreground">
            {seatOf(speaking.role) === "Moderator" ? t("disc.moderator") : speaking.role === GKP ? t("room.gkp") : speaking.role}
          </span>
          {" · "}
          {speaking.text.replace(/\[\d+\]/g, "").replace(/\*\*/g, "")}
        </p>
      ) : (
        <p className="text-center text-xs text-muted-foreground">{t("map.hint")}</p>
      )}
    </div>
  );
}

/** The replay's controls, under the map. */
export function ReplayBar({ replay }: { replay: Replay }) {
  const { t } = useT();
  const done = replay.shown >= replay.total && !replay.playing;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card px-3 py-2">
      <span className="flex min-w-0 flex-1 items-center gap-2 text-sm">
        {done && <CheckCircle2 className="size-4 shrink-0 text-success" />}
        {done ? t("map.done", { n: replay.total }) : t("map.playing", { n: replay.shown, total: replay.total })}
      </span>
      <Button variant="outline" size="icon" aria-label={t("map.first")} disabled={!replay.total} onClick={replay.first}>
        <SkipBack />
      </Button>
      <Button
        size="icon"
        className="rounded-full"
        aria-label={replay.playing ? t("map.pause") : t("map.play")}
        disabled={!replay.total}
        onClick={replay.playing ? replay.pause : replay.play}
      >
        {replay.playing ? <Pause /> : <Play />}
      </Button>
      <Button variant="outline" size="icon" aria-label={t("map.last")} disabled={!replay.total} onClick={replay.last}>
        <SkipForward />
      </Button>
    </div>
  );
}

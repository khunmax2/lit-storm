// The round table of a Discussion (pages/discussion.tsx): who sits at it, who
// spoke last, and what each of them has said so far — the experts' work first,
// the transcript folded below it. Built from the view engines/costorm writes
// beside each finished Turn; nothing here is invented: counts are utterances,
// citations and sources in that view.
//
// useRoom reads the view once; RoomTable (the table and what the picked seat
// said) and RoomWho (each seat's latest line) share its pick, so the page can
// put RoomWho beside the table, in its side column, on wide screens.
import { Loader2 } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

export type RoomTurn = { role: string; role_description: string; type: string; text: string; cited: number[]; warmup: boolean };

const MODERATOR = "Moderator";
const GKP = "General Knowledge Provider";
const GUEST = "Guest";

// The same speaker keeps the same colour through the conversation.
const HUES = ["bg-sky-500", "bg-violet-500", "bg-emerald-500", "bg-amber-500", "bg-rose-500", "bg-teal-500"];
export function hue(role: string) {
  if (role === MODERATOR || role.toLowerCase().includes("moderator")) return "bg-foreground/70";
  if (role === GKP) return "bg-slate-500";
  if (role === GUEST) return "bg-primary";
  let n = 0;
  for (const ch of role) n = (n * 31 + ch.charCodeAt(0)) >>> 0;
  return HUES[n % HUES.length];
}

/** The letter in a seat's circle: Thai roles mostly open with ผู้, นัก or
 *  ตัวแทน, and a leading vowel is no letter to tell people apart by. */
export function initial(name: string) {
  const rest = name.trim().replace(/^(ผู้|นัก|ตัวแทน)/, "").replace(/^[เแโใไ]/, "");
  return (rest || name.trim()).charAt(0).toUpperCase();
}

const KINDS: Record<string, Key> = {
  "Original Question": "room.kind.question",
  "Potential Answer": "room.kind.answer",
  "Further Details": "room.kind.details",
  "Information Request": "room.kind.request",
};
const KIND_TONE: Record<string, string> = {
  "Original Question": "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-200",
  "Potential Answer": "bg-indigo-100 text-indigo-900 dark:bg-indigo-500/15 dark:text-indigo-200",
  "Further Details": "bg-emerald-100 text-emerald-900 dark:bg-emerald-500/15 dark:text-emerald-200",
};

export function KindTag({ type }: { type: string }) {
  const { t } = useT();
  if (!type) return null;
  return (
    <span className={cn("rounded-md px-1.5 py-px text-[11px] font-medium whitespace-nowrap", KIND_TONE[type] ?? "bg-muted text-muted-foreground")}>
      {KINDS[type] ? t(KINDS[type]) : type}
    </span>
  );
}

/** Text without its [n] markers and bold marks, cut to `max` characters. */
function snippet(text: string, max: number) {
  const plain = text.replace(/\[\d+\]/g, "").replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
  return plain.length > max ? `${plain.slice(0, max)}…` : plain;
}

type Seat = {
  role: string;
  name: string;
  description: string;
  said: { index: number; turn: RoomTurn }[];
  // At the table now: the moderator, the experts the view lists, the knowledge provider, the owner.
  // An expert Co-STORM has since replaced is listed apart, as having been there.
  seated: boolean;
};

export type Room = ReturnType<typeof useRoom>;

export function useRoom(turns: RoomTurn[], experts: string[]) {
  const { t } = useT();
  const [picked, setPicked] = useState<string | null>(null);
  const built = useMemo(() => {
    const name = (role: string) =>
      role === MODERATOR ? t("disc.moderator") : role === GKP ? t("room.gkp") : role === GUEST ? t("room.you") : role;
    const spoken = turns.filter((x) => !x.warmup);
    const byRole = new Map<string, Seat>();
    const seat = (role: string, seated: boolean) => {
      let s = byRole.get(role);
      if (!s) {
        s = { role, name: name(role), description: "", said: [], seated };
        byRole.set(role, s);
      }
      s.seated ||= seated;
      return s;
    };
    // The three fixed roles say what they do here; Co-STORM gives the experts their own lines.
    seat(MODERATOR, true).description = t("room.modRole");
    experts.forEach((e) => seat(e, true));
    seat(GKP, true).description = t("room.gkpRole");
    seat(GUEST, true).description = t("room.youRole");
    spoken.forEach((turn, index) => {
      const s = seat(turn.role, false);
      s.said.push({ index, turn });
      if (turn.role_description && ![MODERATOR, GKP, GUEST].includes(turn.role)) s.description = turn.role_description;
    });
    const all = [...byRole.values()];
    return {
      seats: all.filter((s) => s.seated),
      past: all.filter((s) => !s.seated),
      spoken,
      citations: spoken.reduce((a, x) => a + x.cited.length, 0),
    };
  }, [turns, experts, t]);
  const last = built.spoken[built.spoken.length - 1];
  const focusRole = picked ?? last?.role ?? null;
  return {
    ...built,
    last,
    focusRole,
    focus: [...built.seats, ...built.past].find((s) => s.role === focusRole) ?? null,
    pick: (role: string) => setPicked((p) => (p === role ? null : role)),
    status: (s: Seat) =>
      last && s.role === last.role ? t("room.spokeLast") : s.said.length ? t("room.spoke", { n: s.said.length }) : t("room.listening"),
  };
}

function Avatar({ seat, size, ring }: { seat: Seat; size: "lg" | "sm"; ring?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-semibold text-white",
        hue(seat.role),
        size === "lg" ? "size-12 text-base" : "size-8 text-xs",
        ring && "ring-3 ring-brand ring-offset-3 ring-offset-background",
      )}
    >
      {initial(seat.name)}
    </span>
  );
}

/** The table, with what the picked seat (else whoever spoke last) said. */
export function RoomTable({
  room,
  sources,
  topics,
  thinking,
  renderText,
}: {
  room: Room;
  sources: number;
  topics: number;
  /** What the table is doing while a Turn runs ("The table is talking"), else null. */
  thinking: string | null;
  renderText: (text: string) => ReactNode;
}) {
  const { t } = useT();
  const { seats, spoken, last, focus, focusRole } = room;
  const focusSaid = focus?.said[focus.said.length - 1] ?? null;
  return (
    <section aria-labelledby="room-table" className="min-w-0 space-y-3 rounded-2xl border bg-card p-4 shadow-xs">
      <div className="flex items-center justify-between gap-2">
        <h2 id="room-table" className="text-sm font-semibold">
          {t("room.title")}
        </h2>
        <span className="text-xs text-muted-foreground">{t("room.hint")}</span>
      </div>

      <div className="relative hidden h-[25rem] rounded-xl bg-muted/40 sm:block">
        <div aria-hidden className="absolute top-1/2 left-1/2 h-[16rem] w-[24rem] max-w-[70%] -translate-1/2 rounded-[50%] border bg-brand/5" />
        <div className="absolute top-1/2 left-1/2 flex h-32 w-52 -translate-1/2 flex-col items-center justify-center gap-0.5 rounded-[50%] bg-foreground text-center text-background">
          {thinking ? (
            <>
              <Loader2 className="size-5 animate-spin" />
              <span className="px-4 text-xs">{thinking}</span>
            </>
          ) : (
            <>
              <span className="text-[11px] opacity-75">{t("room.base")}</span>
              <span className="text-2xl font-bold">{sources}</span>
              <span className="text-[11px] opacity-75">{t("room.baseSub", { n: topics, c: room.citations })}</span>
            </>
          )}
        </div>
        {seats.map((s, i) => {
          const angle = -Math.PI / 2 + (i * 2 * Math.PI) / seats.length;
          const focused = s.role === focusRole;
          const latest = last && s.role === last.role;
          return (
            <button
              key={s.role}
              type="button"
              aria-pressed={focused}
              onClick={() => room.pick(s.role)}
              style={{ left: `${50 + 40 * Math.cos(angle)}%`, top: `${50 + 39 * Math.sin(angle)}%` }}
              className="absolute flex w-36 -translate-1/2 flex-col items-center gap-1 rounded-xl p-1.5 text-center transition-colors hover:bg-background/70 focus-visible:bg-background/70"
            >
              <span className={cn(!focused && !s.said.length && "opacity-55")}>
                <Avatar seat={s} size="lg" ring={focused} />
              </span>
              <span className="mt-1 line-clamp-2 text-xs leading-snug font-medium">{s.name}</span>
              <span className={cn("rounded-full px-2 text-[11px]", latest ? cn(hue(s.role), "font-medium text-white") : "text-muted-foreground")}>
                {room.status(s)}
              </span>
            </button>
          );
        })}
      </div>

      {focus && (
        <div className="flex gap-3 rounded-xl border bg-muted/30 p-3.5">
          <Avatar seat={focus} size="sm" />
          <div className="min-w-0 space-y-1">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <span className="text-sm font-medium">{focus.name}</span>
              {focusSaid && <KindTag type={focusSaid.turn.type} />}
              <span className="text-muted-foreground">
                {focusSaid
                  ? t(focusSaid.index === spoken.length - 1 ? "room.saidLast" : "room.saidAt", { n: focusSaid.index + 1, c: focusSaid.turn.cited.length })
                  : t("room.notYet")}
              </span>
            </p>
            {focusSaid ? (
              <div className="text-sm leading-relaxed whitespace-pre-wrap">{renderText(focusSaid.turn.text)}</div>
            ) : (
              focus.description && <p className="text-sm text-muted-foreground">{focus.description}</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

/** Each seat with its latest line: what every expert is doing, at a glance. */
export function RoomWho({ room, className }: { room: Room; className?: string }) {
  const { t } = useT();
  const { seats, past, focusRole } = room;
  return (
    <section aria-labelledby="room-who" className={cn("min-w-0 space-y-1.5", className)}>
      <h2 id="room-who" className="text-sm font-semibold">
        {t("room.who")}
      </h2>
      {[...seats, ...past].map((s, i) => {
        const focused = s.role === focusRole;
        const latest = s.said[s.said.length - 1];
        return (
          <div key={s.role}>
            {i === seats.length && <p className="pt-2 pb-1 text-xs text-muted-foreground">{t("room.left")}</p>}
            <button
              type="button"
              aria-pressed={focused}
              onClick={() => room.pick(s.role)}
              className={cn(
                "flex w-full gap-2.5 rounded-xl border p-2.5 text-left transition-colors",
                focused ? "border-brand/40 bg-brand/5" : "border-transparent hover:bg-muted/50",
              )}
            >
              <Avatar seat={s} size="sm" />
              <span className="min-w-0 flex-1 space-y-0.5">
                <span className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="truncate font-medium" title={s.name}>
                    {s.name}
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{room.status(s)}</span>
                </span>
                {s.description && <span className="line-clamp-1 text-xs text-muted-foreground">{s.description}</span>}
                <span className="line-clamp-2 text-xs leading-relaxed text-foreground/85">
                  {latest ? `${t("room.round", { n: latest.index + 1 })} · ${snippet(latest.turn.text, 90)}` : t("room.notYet")}
                </span>
              </span>
            </button>
          </div>
        );
      })}
    </section>
  );
}

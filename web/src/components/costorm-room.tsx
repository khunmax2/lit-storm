// Who sits at a Discussion's round table (pages/discussion.tsx: the side
// column's people card and the 3D table of components/agent-observatory-3d), who spoke last, and what each of
// them has said so far. Built from the view engines/costorm writes beside each
// finished Turn; nothing here is invented: counts are utterances in that view.
import { ChevronDown } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

export type RoomTurn = { role: string; role_description: string; type: string; text: string; cited: number[]; warmup: boolean };

export const MODERATOR = "Moderator";
export const GKP = "General Knowledge Provider";
export const GUEST = "Guest";

// The same speaker keeps the same colour everywhere: the transcript, the cards
// and the 3D table (components/agent-observatory-3d) all take it from here.
const TONES = ["#f59e0b", "#a78bfa", "#38bdf8", "#fb7185", "#34d399", "#f472b6", "#fb923c"];
export function tone(role: string) {
  if (role === MODERATOR || role.toLowerCase().includes("moderator")) return "#64748b";
  if (role === GKP) return "#14b8a6";
  if (role === GUEST) return "#22c55e";
  // The warm start's background expert is nobody at the table: a quiet slate, dark enough for a white letter.
  if (role.toLowerCase().startsWith("background discussion expert")) return "#5b6b94";
  let n = 0;
  for (const ch of role) n = (n * 31 + ch.charCodeAt(0)) >>> 0;
  return TONES[n % TONES.length];
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
    };
  }, [turns, experts, t]);
  const last = built.spoken[built.spoken.length - 1];
  const focusRole = picked ?? last?.role ?? null;
  return {
    ...built,
    last,
    // Picked by the owner (a card, or a seat on the 3D table); null: nobody, the latest speaker shows.
    picked,
    focusRole,
    focus: [...built.seats, ...built.past].find((s) => s.role === focusRole) ?? null,
    pick: (role: string) => setPicked((p) => (p === role ? null : role)),
    status: (s: Seat) =>
      last && s.role === last.role ? t("room.spokeLast") : s.said.length ? t("room.spoke", { n: s.said.length }) : t("room.listening"),
  };
}

export function isFixed(role: string) {
  return role === MODERATOR || role === GKP || role === GUEST;
}

function Avatar({ seat }: { seat: Seat }) {
  return (
    <span
      aria-hidden
      className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
      style={{ background: tone(seat.role) }}
    >
      {initial(seat.name)}
    </span>
  );
}

function PersonRow({ room, seat, renderText, you }: { room: Room; seat: Seat; renderText: (text: string) => ReactNode; you?: boolean }) {
  const { t } = useT();
  const picked = room.picked === seat.role;
  const latest = seat.said[seat.said.length - 1];
  // The three fixed roles say what they do; an expert says what it said last, or that it has not yet.
  const line = isFixed(seat.role) ? seat.description : latest ? snippet(latest.turn.text, 110) : t("room.notYet");
  return (
    <button
      type="button"
      aria-pressed={picked}
      onClick={() => room.pick(seat.role)}
      className={cn(
        "flex w-full gap-2.5 rounded-xl border p-2.5 text-left transition-[background-color,box-shadow]",
        picked ? "border-brand bg-brand/5 ring-3 ring-brand/15" : you ? "border-success/25 bg-success/5 hover:bg-success/10" : "bg-card hover:bg-muted/50",
      )}
    >
      <Avatar seat={seat} />
      <span className="min-w-0 flex-1 space-y-0.5">
        <span className="flex items-start justify-between gap-2">
          <span className="text-sm leading-snug font-medium">{seat.name}</span>
          {!isFixed(seat.role) && (
            <span className="mt-0.5 shrink-0 rounded-full bg-muted px-2 py-px text-[11px] text-muted-foreground">{room.status(seat)}</span>
          )}
        </span>
        {picked && latest ? (
          <span className="block space-y-1 pt-0.5">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {t("room.round", { n: latest.index + 1 })}
              <KindTag type={latest.turn.type} />
            </span>
            <span className="block text-sm leading-relaxed whitespace-pre-wrap">{renderText(latest.turn.text)}</span>
          </span>
        ) : (
          line && <span className="line-clamp-2 text-xs text-muted-foreground">{line}</span>
        )}
      </span>
    </button>
  );
}

/** Who is at the table, in the side column: the experts, the two who help the
 *  table along, and the owner. A seat picked here or on the map is picked
 *  everywhere, and shows its latest line in full. */
export function RoomPeople({ room, renderText }: { room: Room; renderText: (text: string) => ReactNode }) {
  const { t } = useT();
  const experts = room.seats.filter((s) => !isFixed(s.role));
  const helpers = room.seats.filter((s) => s.role === MODERATOR || s.role === GKP);
  const you = room.seats.find((s) => s.role === GUEST);
  const [helpersOpen, setHelpersOpen] = useState(true);
  const group = "rounded-lg bg-muted/60 px-2.5 py-1 text-xs font-semibold";
  return (
    <div className="space-y-2">
      <p className={group}>
        {t("room.expertsGroup")} <span className="font-normal text-muted-foreground">· {t("map.roles", { n: experts.length })}</span>
      </p>
      {experts.map((s) => (
        <PersonRow key={s.role} room={room} seat={s} renderText={renderText} />
      ))}
      {room.past.length > 0 && (
        <>
          <p className="px-1 pt-1 text-xs text-muted-foreground">{t("room.left")}</p>
          {room.past.map((s) => (
            <PersonRow key={s.role} room={room} seat={s} renderText={renderText} />
          ))}
        </>
      )}
      <button
        type="button"
        aria-expanded={helpersOpen}
        onClick={() => setHelpersOpen((o) => !o)}
        className={cn(group, "flex w-full items-center justify-between text-left")}
      >
        {t("room.helpers")}
        <ChevronDown className={cn("size-3.5 text-muted-foreground transition-transform", !helpersOpen && "-rotate-90")} />
      </button>
      {(helpersOpen || helpers.some((s) => s.role === room.picked)) &&
        helpers.map((s) => <PersonRow key={s.role} room={room} seat={s} renderText={renderText} />)}
      {you && <PersonRow room={room} seat={you} renderText={renderText} you />}
    </div>
  );
}

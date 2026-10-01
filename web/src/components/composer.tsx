// The research composer: a tray of choices around a white box for the topic,
// the model beside the send button — the layout agent apps have settled on. Used on the home page (with
// a project picker) and at the foot of a topic (to research it again).
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  Gauge,
  Globe,
  ListOrdered,
  Loader2,
  MessageCircleQuestion,
  Search,
  SendHorizontal,
  Sparkles,
  Telescope,
  Timer,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { api, call } from "@/api/client";
import { ErrorText } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

export type Depth = "fast" | "standard" | "deep";
const DEPTHS: Depth[] = ["fast", "standard", "deep"];
export type RunForm = {
  topic: string;
  language: string;
  llm_model_id: string;
  search_provider_id: string;
  depth: Depth;
  engine: string;
  // Clarifying questions and the owner's answers, when they asked for them.
  refinement?: { question: string; answer: string }[];
  // More Search Providers searched beside the first, for a mode that can.
  extra_search_provider_ids?: string[];
  // The report's sections, one per line, and whether the mode at this depth
  // uses them (the composer sets it): typed text is kept when it does not.
  sections_text?: string;
  sections_on?: boolean;
};

// One press of Start is one Run: the same key goes with every retry of the
// request, and a new key is made only after the Run was created.
export function useRequestKey() {
  const key = useRef("");
  if (!key.current) key.current = newKey();
  return { current: () => key.current, next: () => (key.current = newKey()) };
}

// crypto.randomUUID exists only on HTTPS and localhost. Opened over plain
// HTTP by address, every page with a composer failed to render without it.
function newKey() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function runBody(form: RunForm, request_key: string) {
  return {
    topic: form.topic.trim(),
    language: form.language,
    llm_model_id: form.llm_model_id || null,
    search_provider_id: form.search_provider_id || null,
    depth: form.depth,
    engine: form.engine,
    refinement: (form.refinement ?? []).filter((qa) => qa.answer.trim()),
    extra_search_provider_ids: form.extra_search_provider_ids ?? [],
    sections: form.sections_on ? (form.sections_text ?? "").split("\n").filter((l) => l.trim()) : [],
    request_key,
  };
}

/** Start research: a Discussion for Co-STORM, which talks in Turns;
 *  otherwise a Research Session with its first Run. Both answer with the
 *  Session's id, which is where the page goes next. */
export function startResearch(form: RunForm, request_key: string, project_id?: string): Promise<{ id: string }> {
  if (form.engine === "co-storm") {
    const { topic, language, llm_model_id, search_provider_id, depth } = runBody(form, request_key);
    return call(
      api.POST("/api/discussions", {
        body: { topic, language, llm_model_id, search_provider_id, depth, project_id: project_id ?? null, request_key },
      }),
    );
  }
  if (project_id)
    return call(
      api.POST("/api/projects/{project_id}/sessions", { params: { path: { project_id } }, body: runBody(form, request_key) }),
    );
  return call(api.POST("/api/sessions", { body: runBody(form, request_key) }));
}

export function useRunOptions() {
  return useQuery({ queryKey: ["options"], queryFn: () => call(api.GET("/api/options")) });
}

/** The level's usual time: the clock and the minutes, the words before
 *  them sliding out on hover or a tap. */
function Estimate({ minutes }: { minutes: number }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  return (
    <button
      type="button"
      aria-label={t("depth.estimate", { n: minutes })}
      aria-expanded={open}
      onClick={() => setOpen(!open)}
      onBlur={() => setOpen(false)}
      className="group/est flex items-center rounded-md px-1 py-1 text-xs whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <Timer className="mr-1 size-3.5" />
      <span
        aria-hidden
        className="max-w-0 overflow-hidden opacity-0 transition-[max-width,opacity] duration-300 ease-out group-hover/est:max-w-32 group-hover/est:opacity-100 group-aria-expanded/est:max-w-32 group-aria-expanded/est:opacity-100 motion-reduce:transition-none"
      >
        {t("depth.estimatePrefix")}&nbsp;
      </span>
      <span key={minutes} aria-hidden className="animate-in duration-300 fade-in-0 motion-reduce:animate-none">
        {t("depth.minutesShort", { n: minutes })}
      </span>
    </button>
  );
}

/** What is left of the month's Runs, as a bar; the words show on hover or
 *  a tap. Out of Runs, the reason stays in words. */
export function QuotaLine({ className }: { className?: string }) {
  const { t } = useT();
  const quota = useQuery({ queryKey: ["quota"], queryFn: () => call(api.GET("/api/me/quota")) });
  const [open, setOpen] = useState(false);
  const q = quota.data;
  if (!q) return null;
  if (q.remaining === 0 && q.reserved === 0) return <p className={cn("text-xs text-warning", className)}>{t("quota.full")}</p>;
  const share = q.limit > 0 ? Math.min(1, q.remaining / q.limit) : 0;
  const low = share <= 0.1;
  const words = t("quota.tip", { remaining: q.remaining, limit: q.limit });
  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={q.reserved > 0 ? `${words} · ${t("quota.reserved", { reserved: q.reserved })}` : words}
          // A tap keeps it open rather than the trigger's own close on press.
          onPointerDown={(e) => e.preventDefault()}
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "inline-flex items-center gap-2 rounded-md px-1.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
            className,
          )}
        >
          {t("quota.label")}:
          <span className="relative h-1.5 w-28 overflow-hidden rounded-full bg-muted-foreground/15">
            <span
              className={cn(
                "absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none",
                low ? "bg-warning" : "bg-brand",
              )}
              style={{ width: `${share * 100}%` }}
            />
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent className="flex-col items-start gap-0.5">
        <span>{words}</span>
        {q.reserved > 0 && <span className="opacity-70">{t("quota.reserved", { reserved: q.reserved })}</span>}
      </TooltipContent>
    </Tooltip>
  );
}

// A choice in the composer's tray: a small white button with a hairline
// border that lifts under the pointer, gives a little when pressed and stays
// lit while its menu is open.
export const CHIP = cn(
  "h-8 gap-1.5 rounded-lg border border-input bg-background px-2.5 text-[13px] font-normal shadow-xs dark:bg-input/30",
  "transition-[background-color,box-shadow,transform,color] duration-200 ease-out",
  "hover:-translate-y-px hover:bg-muted/60 hover:shadow-sm active:translate-y-0 active:scale-[0.96] dark:hover:bg-input/50",
  "aria-expanded:bg-muted/70 aria-expanded:shadow-sm",
  "motion-reduce:transform-none motion-reduce:transition-none",
);
// A chip whose last icon is a chevron: it turns over while the menu is open.
const FLIP = "[&>svg:last-child]:transition-transform [&>svg:last-child]:duration-300 aria-expanded:[&>svg:last-child]:rotate-180";
// The composer's menus open a little slower than the kit's, and ease out.
const MENU = "duration-200 ease-out";
// Menu rows: the highlight fades rather than jumps; a tick pops in.
const ITEM = cn(
  "transition-colors duration-150",
  "[&_[data-slot$=indicator]_svg]:animate-in [&_[data-slot$=indicator]_svg]:zoom-in-50 [&_[data-slot$=indicator]_svg]:fade-in-0 [&_[data-slot$=indicator]_svg]:duration-200",
);

function Chip({
  icon,
  value,
  onChange,
  items,
  label,
  compact,
  heading,
  hint,
}: {
  icon: ReactNode;
  value: string;
  onChange: (v: string) => void;
  items: { value: string; label: string }[];
  label: string;
  /** Only the icon, no chevron, until pointed at or opened; the name slides out then. */
  compact?: boolean;
  /** What the choice is for, above the choices; `hint` says more, smaller. */
  heading?: string;
  hint?: string;
}) {
  return (
    // Radix may echo a value while its items mount; passing that on would
    // write a stale copy of the form over the defaults just chosen.
    <Select value={value} onValueChange={(v) => v && v !== value && onChange(v)}>
      <SelectTrigger size="sm" aria-label={label} className={cn(CHIP, FLIP, "data-[size=sm]:h-8 data-[size=sm]:rounded-lg", compact && "group/chip justify-center px-[8.5px] [&>svg:last-child]:hidden")}>
        {icon}
        {/* Radix drops a className on SelectValue: the sliding is on a wrapper. */}
        {compact ? (
          <span className="-ml-1.5 flex max-w-0 overflow-hidden whitespace-nowrap opacity-0 transition-[max-width,opacity,margin] duration-300 ease-out group-hover/chip:mr-0.5 group-hover/chip:ml-0 group-hover/chip:max-w-56 group-hover/chip:opacity-100 group-focus-visible/chip:mr-0.5 group-focus-visible/chip:ml-0 group-focus-visible/chip:max-w-56 group-focus-visible/chip:opacity-100 group-aria-expanded/chip:mr-0.5 group-aria-expanded/chip:ml-0 group-aria-expanded/chip:max-w-56 group-aria-expanded/chip:opacity-100 motion-reduce:transition-none">
            <SelectValue />
          </span>
        ) : (
          <SelectValue />
        )}
      </SelectTrigger>
      <SelectContent className={MENU}>
        <SelectGroup>
          {heading && (
            <SelectLabel className="max-w-60 px-2 pt-1.5 pb-1">
              <span className="block text-xs font-medium text-foreground">{heading}</span>
              {hint && <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">{hint}</span>}
            </SelectLabel>
          )}
          {items.map((i) => (
            <SelectItem key={i.value} value={i.value} className={ITEM}>
              {i.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

const DEPTH_ICON: Record<Depth, LucideIcon> = { fast: Zap, standard: Gauge, deep: Telescope };

/** The depth: the menu names each level with a line on what it means and
 *  how long it usually takes; once chosen, the chip keeps only its icon
 *  (the name shows on hover). */
function DepthPicker({
  value,
  onChange,
  minutes,
}: {
  value: Depth;
  onChange: (d: Depth) => void;
  minutes: (d: Depth) => number;
}) {
  const { t } = useT();
  const Icon = DEPTH_ICON[value];
  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn(CHIP, "w-8 px-0")}
              aria-label={`${t("depth.label")}: ${t(`depth.${value}`)}`}
            >
              {/* A new level's icon pops in, so the change is seen. */}
              <Icon key={value} className="size-4 animate-in duration-300 zoom-in-50 fade-in-0 motion-reduce:animate-none" />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>{t(`depth.${value}`)}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="start" className={cn(MENU, "w-80 rounded-2xl p-1.5")}>
        <DropdownMenuRadioGroup value={value} onValueChange={(v) => v !== value && onChange(v as Depth)}>
          {DEPTHS.map((d) => {
            const I = DEPTH_ICON[d];
            return (
              <DropdownMenuRadioItem
                key={d}
                value={d}
                className={cn(ITEM, "group/row items-start gap-3 rounded-xl py-2.5 pr-8 pl-3")}
              >
                <I className="mt-0.5 size-[18px] text-foreground transition-transform duration-200 group-focus/row:scale-110" />
                <span className="grid gap-0.5">
                  <span className="font-medium">{t(`depth.${d}`)}</span>
                  <span className="text-xs leading-snug text-muted-foreground">
                    {t(`depth.lead.${d}`)} · {t("depth.minutes", { n: minutes(d) })}
                  </span>
                </span>
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Where it searches, ticked in one menu: the first ticked is the main
 *  Search Provider, the rest are searched beside it, up to what the mode
 *  can use (STORM: three in all). A mode that searches one swaps instead. */
function SearchPicker({
  providers,
  main,
  extra,
  max,
  onChange,
}: {
  providers: { id: string; label: string }[];
  main: string;
  extra: string[];
  max: number;
  onChange: (main: string, extra: string[]) => void;
}) {
  const { t } = useT();
  const chosen = [main, ...extra].filter(Boolean);
  const label = providers.find((p) => p.id === main)?.label ?? t("run.search");
  const toggle = (id: string, on: boolean) => {
    let next: string[];
    if (on) next = max <= 1 ? [id] : chosen.length < max ? [...chosen, id] : chosen;
    // One stays ticked: a Run searches somewhere.
    else next = chosen.length > 1 ? chosen.filter((x) => x !== id) : chosen;
    if (next !== chosen) onChange(next[0], next.slice(1));
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn(CHIP, FLIP, "max-w-64")}
          aria-label={`${t("run.search")}: ${label}`}
        >
          <Search className="size-3.5" />
          <span className="truncate">{label}</span>
          {extra.length > 0 && (
            <span
              key={extra.length}
              className="rounded-md bg-brand-soft px-1.5 text-xs text-brand animate-in duration-200 zoom-in-75 fade-in-0 motion-reduce:animate-none"
            >
              +{extra.length}
            </span>
          )}
          <ChevronDown className="size-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={cn(MENU, "w-72 rounded-xl p-1.5")}>
        <DropdownMenuLabel className="text-xs leading-snug font-normal text-muted-foreground">
          {max > 1 ? t("run.sourcesLead", { n: max }) : t("run.search")}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {providers.map((p) => {
          const on = chosen.includes(p.id);
          return (
            <DropdownMenuCheckboxItem
              key={p.id}
              checked={on}
              disabled={max > 1 && !on && chosen.length >= max}
              // Several can be ticked: the menu stays open between them.
              onSelect={(e) => max > 1 && e.preventDefault()}
              onCheckedChange={(checked) => toggle(p.id, checked)}
              className={cn(ITEM, "rounded-lg py-1.5 pl-2.5")}
            >
              <span className="truncate">{p.label}</span>
              {max > 1 && chosen.length > 1 && p.id === main && (
                <span className="ml-auto rounded bg-muted px-1.5 text-[11px] text-muted-foreground">{t("run.sourceMain")}</span>
              )}
            </DropdownMenuCheckboxItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function Composer({
  form,
  setForm,
  onSubmit,
  pending,
  extra,
  autoFocus,
  size = "lg",
  locked,
}: {
  form: RunForm;
  setForm: (f: RunForm) => void;
  onSubmit: () => void;
  pending: boolean;
  extra?: ReactNode;
  autoFocus?: boolean;
  size?: "lg" | "md";
  /** Why this composer cannot start a Run yet; shows instead of the send button. */
  locked?: ReactNode;
}) {
  const { t } = useT();
  const options = useRunOptions();
  const o = options.data;
  const [focused, setFocused] = useState(false);

  // Only what the mode can use (docs/web-app-design.md, รุ่นสอง: กติกาที่ทุก
  // Engine ใช้ร่วมกัน): its Search Provider kinds, and models that call tools
  // when it drives tools.
  const engine = o?.engines.find((e) => e.id === form.engine);
  const models = o?.models.filter((m) => !engine?.needs_tools || m.supports_tools === true) ?? [];
  const providers = o?.search_providers.filter((p) => !engine || engine.search_kinds.includes(p.kind)) ?? [];

  // The owner's headings (docs/web-app-design.md, หัวข้อที่ต้องการ): where the
  // mode at this depth uses them.
  const sectionsOn = !!engine?.sections_at?.includes(form.depth);
  // Open at first when headings came filled in (research again).
  const [sectionsOpen, setSectionsOpen] = useState(() => !!form.sections_text?.trim());

  useEffect(() => {
    // One update for all of it: two effects each writing a copy of the same
    // form in one render lost the first's changes (the defaults, when the
    // mode takes sections at this depth — search and model showed empty).
    const patch: Partial<RunForm> = {};
    if (!!form.sections_on !== sectionsOn) patch.sections_on = sectionsOn;
    // Preselect the defaults once options arrive (design: หน้าเริ่มวิจัยเลือก default ไว้ให้),
    // and again when a new mode cannot use what was chosen. A choice still
    // allowed is kept, so running this again changes nothing.
    if (o) {
      const pick = <T extends { id: string; is_default: boolean }>(list: T[], current: string) =>
        list.some((x) => x.id === current) ? current : (list.find((x) => x.is_default)?.id ?? list[0]?.id ?? "");
      const model = pick(models, form.llm_model_id);
      const search = pick(providers, form.search_provider_id);
      const extra = (form.extra_search_provider_ids ?? [])
        .filter((id) => id !== search && providers.some((p) => p.id === id))
        .slice(0, (engine?.max_sources ?? 1) - 1);
      if (
        model !== form.llm_model_id ||
        search !== form.search_provider_id ||
        extra.length !== (form.extra_search_provider_ids ?? []).length
      )
        Object.assign(patch, { llm_model_id: model, search_provider_id: search, extra_search_provider_ids: extra });
    }
    if (Object.keys(patch).length) setForm({ ...form, ...patch });
  }, [o, form.engine, sectionsOn, form.sections_on]); // eslint-disable-line react-hooks/exhaustive-deps

  const unavailable = o && (models.length === 0 || providers.length === 0);
  // Each level's time target, as the Administrator set it.
  const minutes = (d: Depth) => o?.depth_levels.find((x) => x.id === d)?.target_minutes ?? 5;
  const ready = form.topic.trim().length >= 3 && !unavailable && !pending && !locked;
  const showSections = sectionsOn && sectionsOpen;
  // Headings typed in are used whether the panel shows or not; the chip says so.
  const sectionCount = (form.sections_text ?? "").split("\n").filter((l) => l.trim()).length;
  const sectionsSet = sectionsOn && sectionCount > 0;

  // Question refinement (docs/web-app-design.md, ขัดเกลาโจทย์): a few
  // questions from the chosen model, answered or skipped, before starting.
  const refine = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/refine", {
          body: { topic: form.topic.trim(), language: form.language, llm_model_id: form.llm_model_id || null },
        }),
      ),
    onSuccess: (r) => setForm({ ...form, refinement: r.questions.map((question) => ({ question, answer: "" })) }),
  });
  const qa = form.refinement ?? [];
  const setAnswer = (i: number, answer: string) =>
    setForm({ ...form, refinement: qa.map((x, j) => (j === i ? { ...x, answer } : x)) });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onSubmit();
      }}
      className="rounded-2xl border bg-muted/60 p-1.5 shadow-xs dark:bg-muted/30"
    >
      <div className="flex flex-wrap items-center gap-1.5 px-1 pt-0.5 pb-2">
        <Chip
          label={t("run.language")}
          heading={t("run.languageHeading")}
          hint={t("run.languageHint")}
          icon={<Globe className="size-3.5" />}
          value={form.language}
          onChange={(language) => setForm({ ...form, language })}
          items={[
            { value: "th", label: t("lang.th") },
            { value: "en", label: t("lang.en") },
          ]}
        />
        {providers.length > 0 && (
          <SearchPicker
            providers={providers}
            main={form.search_provider_id}
            extra={form.extra_search_provider_ids ?? []}
            max={engine?.max_sources ?? 1}
            onChange={(search_provider_id, extra_search_provider_ids) =>
              setForm({ ...form, search_provider_id, extra_search_provider_ids })
            }
          />
        )}
        <DepthPicker value={form.depth} onChange={(depth) => setForm({ ...form, depth })} minutes={minutes} />
        {sectionsOn && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn(
              CHIP,
              "transition-[background-color,box-shadow,transform,color,border-color]",
              showSections && "bg-muted hover:bg-muted",
              sectionsSet && "border-brand text-brand shadow-[0_0_0_3px_var(--brand-soft)] hover:text-brand dark:border-brand",
            )}
            aria-expanded={showSections}
            title={sectionsSet ? t("sections.set", { n: sectionCount }) : undefined}
            onClick={() => setSectionsOpen(!showSections)}
          >
            <ListOrdered
              className={cn("size-3.5 transition-colors duration-200", (showSections || sectionsSet) && "text-brand")}
            />
            {t("sections.chip")}
            {sectionsSet && (
              <span
                key={sectionCount}
                className="rounded-md bg-brand-soft px-1.5 text-xs animate-in duration-200 zoom-in-75 fade-in-0 motion-reduce:animate-none"
              >
                {sectionCount}
              </span>
            )}
          </Button>
        )}
        {extra}
      </div>
      <div
        className={cn(
          "rounded-xl border bg-card shadow-sm transition-shadow",
          focused && "shadow-md ring-3 ring-ring/15",
        )}
      >
        <div className="px-4 pt-4">
          <Textarea
            autoFocus={autoFocus}
            value={form.topic}
            onChange={(e) => setForm({ ...form, topic: e.target.value })}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                if (ready) onSubmit();
              }
            }}
            placeholder={t("home.placeholder")}
            maxLength={500}
            className={cn(
              "resize-none rounded-none border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 dark:bg-transparent",
              size === "lg" ? "min-h-20 text-base md:text-base" : "min-h-12",
            )}
          />
        </div>
        {showSections && (
          <div className="mx-3 mt-3 grid gap-1.5 rounded-lg border bg-muted/40 p-3 text-sm animate-in duration-300 ease-out fade-in-0 slide-in-from-top-2 motion-reduce:animate-none">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 font-medium">
                <ListOrdered className="size-4 text-brand" />
                {t("sections.title")}
              </span>
              <span className="flex items-center gap-0.5">
                {sectionCount > 0 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-muted-foreground animate-in fade-in-0"
                    onClick={() => setForm({ ...form, sections_text: "" })}
                  >
                    {t("sections.clear")}
                  </Button>
                )}
                {/* Hides the panel; headings typed in are still used. */}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7 transition-transform duration-200 hover:rotate-90 motion-reduce:transform-none"
                  aria-label={t("sections.hide")}
                  title={t("sections.hide")}
                  onClick={() => setSectionsOpen(false)}
                >
                  <X />
                </Button>
              </span>
            </div>
            <span className="text-xs text-muted-foreground">{t("sections.lead")}</span>
            <textarea
              aria-label={t("sections.title")}
              className="min-h-24 rounded-md border bg-background px-2.5 py-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/20"
              value={form.sections_text ?? ""}
              placeholder={t("sections.placeholder")}
              onChange={(e) => setForm({ ...form, sections_text: e.target.value })}
            />
          </div>
        )}
        {(qa.length > 0 || refine.error) && (
          <div className="mx-3 mt-3 grid gap-2.5 rounded-lg border bg-muted/40 p-3 animate-in duration-300 ease-out fade-in-0 slide-in-from-top-2 motion-reduce:animate-none">
            <div className="flex items-center justify-between gap-2 text-sm font-medium">
              <span className="flex items-center gap-1.5">
                <MessageCircleQuestion className="size-4 text-brand" />
                {t("refine.title")}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label={t("refine.clear")}
                onClick={() => {
                  refine.reset();
                  setForm({ ...form, refinement: [] });
                }}
              >
                <X />
              </Button>
            </div>
            {!!refine.error && <ErrorText error={refine.error} />}
            {qa.map((x, i) => (
              <label key={i} className="grid gap-1 text-sm">
                <span className="text-muted-foreground">{x.question}</span>
                <input
                  className="h-8 rounded-md border bg-background px-2.5 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/20"
                  value={x.answer}
                  placeholder={t("refine.skip")}
                  onChange={(e) => setAnswer(i, e.target.value)}
                />
              </label>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2 px-3 pt-2 pb-3">
          {models.length > 0 && (
            <Chip
              label={t("run.model")}
              icon={<Sparkles className="size-3.5 text-brand" />}
              value={form.llm_model_id}
              onChange={(llm_model_id) => setForm({ ...form, llm_model_id })}
              items={models.map((m) => ({ value: m.id, label: m.label }))}
              compact
            />
          )}
          <div className="ml-auto flex items-center gap-3">
            {/* A Discussion is steered as it goes; it has no questions up front. */}
            {!locked && qa.length === 0 && form.engine !== "co-storm" && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 text-[13px] text-muted-foreground transition-[background-color,color,transform] duration-200 active:scale-[0.96] motion-reduce:transform-none"
                disabled={!ready || refine.isPending}
                onClick={() => refine.mutate()}
              >
                {refine.isPending ? <Loader2 className="animate-spin" /> : <MessageCircleQuestion />}
                {t("refine.ask")}
              </Button>
            )}
            {locked ? (
              <span className="text-xs text-muted-foreground">{locked}</span>
            ) : (
              <Estimate minutes={minutes(form.depth)} />
            )}
            {/* Lights up once there is a topic; leans forward under the pointer. */}
            <Button
              type="submit"
              size="icon"
              className={cn(
                "size-9 rounded-lg transition-[background-color,box-shadow,transform,opacity] duration-300 ease-out",
                "hover:scale-105 hover:shadow-md active:scale-95 [&_svg]:transition-transform [&_svg]:duration-300 hover:[&_svg]:translate-x-0.5",
                "motion-reduce:transform-none motion-reduce:[&_svg]:transform-none",
              )}
              disabled={!ready}
              aria-label={t("run.start")}
            >
              {pending ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
            </Button>
          </div>
        </div>
      </div>
      {unavailable && <p className="px-3 pt-2 text-sm text-warning">{t("run.noOptions")}</p>}
    </form>
  );
}

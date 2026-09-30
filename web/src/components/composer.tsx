// The research composer: a tray of choices around a white box for the topic,
// the model beside the send button — the layout agent apps have settled on. Used on the home page (with
// a project picker) and at the foot of a topic (to research it again).
import { useMutation, useQuery } from "@tanstack/react-query";
import { Gauge, Globe, ListOrdered, Loader2, MessageCircleQuestion, Plus, Search, SendHorizontal, Sparkles, Timer, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { api, call } from "@/api/client";
import { ErrorText } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
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

export function QuotaLine({ className }: { className?: string }) {
  const { t } = useT();
  const quota = useQuery({ queryKey: ["quota"], queryFn: () => call(api.GET("/api/me/quota")) });
  const q = quota.data;
  if (!q) return null;
  const full = q.remaining === 0;
  return (
    <p className={cn("text-xs", full ? "text-warning" : "text-muted-foreground", className)}>
      {full && q.reserved === 0 ? t("quota.full") : t("quota.line", { remaining: q.remaining, limit: q.limit })}
      {q.reserved > 0 && ` · ${t("quota.reserved", { reserved: q.reserved })}`}
    </p>
  );
}

// A choice in the composer's tray: a small white button with a hairline border.
export const CHIP =
  "h-8 gap-1.5 rounded-lg border bg-background px-2.5 text-[13px] font-normal shadow-xs hover:bg-muted/60 dark:bg-card";

function Chip({
  icon,
  value,
  onChange,
  items,
  label,
}: {
  icon: ReactNode;
  value: string;
  onChange: (v: string) => void;
  items: { value: string; label: string }[];
  label: string;
}) {
  return (
    // Radix may echo a value while its items mount; passing that on would
    // write a stale copy of the form over the defaults just chosen.
    <Select value={value} onValueChange={(v) => v && v !== value && onChange(v)}>
      <SelectTrigger
        size="sm"
        aria-label={label}
        className={CHIP}
      >
        {icon}
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {items.map((i) => (
          <SelectItem key={i.value} value={i.value}>
            {i.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** Other Search Providers to search beside the first (STORM: up to two more). */
function MoreSources({
  providers,
  chosen,
  room,
  onChange,
}: {
  providers: { id: string; label: string }[];
  chosen: string[];
  room: number;
  onChange: (ids: string[]) => void;
}) {
  const { t } = useT();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="sm" className={CHIP} aria-label={t("run.moreSources")}>
          <Plus className="size-3.5" />
          {chosen.length ? t("run.moreSourcesN", { n: chosen.length }) : t("run.moreSources")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          {t("run.moreSourcesLead", { n: room })}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {providers.map((p) => {
          const on = chosen.includes(p.id);
          return (
            <DropdownMenuCheckboxItem
              key={p.id}
              checked={on}
              disabled={!on && chosen.length >= room}
              onSelect={(e) => e.preventDefault()}
              onCheckedChange={(checked) => onChange(checked ? [...chosen, p.id] : chosen.filter((id) => id !== p.id))}
            >
              {p.label}
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

  useEffect(() => {
    // Preselect the defaults once options arrive (design: หน้าเริ่มวิจัยเลือก default ไว้ให้),
    // and again when a new mode cannot use what was chosen.
    if (!o) return;
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
      setForm({ ...form, llm_model_id: model, search_provider_id: search, extra_search_provider_ids: extra });
  }, [o, form.engine]); // eslint-disable-line react-hooks/exhaustive-deps

  const unavailable = o && (models.length === 0 || providers.length === 0);
  // The level's time target, as the Administrator set it.
  const target = o?.depth_levels.find((d) => d.id === form.depth)?.target_minutes ?? 5;
  const ready = form.topic.trim().length >= 3 && !unavailable && !pending && !locked;
  // The owner's headings (docs/web-app-design.md, หัวข้อที่ต้องการ): where the
  // mode at this depth uses them.
  const sectionsOn = !!engine?.sections_at?.includes(form.depth);
  const [sectionsOpen, setSectionsOpen] = useState(false);
  useEffect(() => {
    if (!!form.sections_on !== sectionsOn) setForm({ ...form, sections_on: sectionsOn });
  }, [sectionsOn, form.sections_on]); // eslint-disable-line react-hooks/exhaustive-deps
  const showSections = sectionsOn && (sectionsOpen || !!form.sections_text?.trim());

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
          icon={<Globe className="size-3.5" />}
          value={form.language}
          onChange={(language) => setForm({ ...form, language })}
          items={[
            { value: "th", label: t("lang.th") },
            { value: "en", label: t("lang.en") },
          ]}
        />
        {providers.length > 0 && (
          <Chip
            label={t("run.search")}
            icon={<Search className="size-3.5" />}
            value={form.search_provider_id}
            onChange={(search_provider_id) =>
              setForm({
                ...form,
                search_provider_id,
                extra_search_provider_ids: (form.extra_search_provider_ids ?? []).filter((id) => id !== search_provider_id),
              })
            }
            items={providers.map((p) => ({ value: p.id, label: p.label }))}
          />
        )}
        {(engine?.max_sources ?? 1) > 1 && providers.length > 1 && (
          <MoreSources
            providers={providers.filter((p) => p.id !== form.search_provider_id)}
            chosen={form.extra_search_provider_ids ?? []}
            room={(engine?.max_sources ?? 1) - 1}
            onChange={(extra_search_provider_ids) => setForm({ ...form, extra_search_provider_ids })}
          />
        )}
        <Chip
          label={t("depth.label")}
          icon={<Gauge className="size-3.5" />}
          value={form.depth}
          onChange={(depth) => setForm({ ...form, depth: depth as Depth })}
          items={DEPTHS.map((d) => ({ value: d, label: t(`depth.${d}`) }))}
        />
        {sectionsOn && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn(CHIP, showSections && "bg-muted")}
            aria-expanded={showSections}
            onClick={() => setSectionsOpen(!showSections)}
          >
            <ListOrdered className="size-3.5" />
            {t("sections.chip")}
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
        <div className="flex items-start gap-3 px-4 pt-4">
          <span
            aria-hidden
            className="mt-1 size-5 shrink-0 rounded-full bg-linear-to-br from-sky-300 via-fuchsia-300 to-amber-200 shadow-[inset_0_-2px_4px_rgb(0_0_0/0.08)]"
          />
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
          <label className="mx-3 mt-3 grid gap-1.5 rounded-lg border bg-muted/40 p-3 text-sm">
            <span className="flex items-center gap-1.5 font-medium">
              <ListOrdered className="size-4 text-brand" />
              {t("sections.title")}
            </span>
            <span className="text-xs text-muted-foreground">{t("sections.lead")}</span>
            <textarea
              className="min-h-24 rounded-md border bg-background px-2.5 py-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/20"
              value={form.sections_text ?? ""}
              placeholder={t("sections.placeholder")}
              onChange={(e) => setForm({ ...form, sections_text: e.target.value })}
            />
          </label>
        )}
        {(qa.length > 0 || refine.error) && (
          <div className="mx-3 mt-3 grid gap-2.5 rounded-lg border bg-muted/40 p-3">
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
            />
          )}
          <div className="ml-auto flex items-center gap-3">
            {/* A Discussion is steered as it goes; it has no questions up front. */}
            {!locked && qa.length === 0 && form.engine !== "co-storm" && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 text-[13px] text-muted-foreground"
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
              <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                <Timer className="size-3.5" />
                {t("depth.estimate", { n: target })}
              </span>
            )}
            <Button type="submit" size="icon" className="size-9 rounded-lg" disabled={!ready} aria-label={t("run.start")}>
              {pending ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
            </Button>
          </div>
        </div>
      </div>
      {unavailable && <p className="px-3 pt-2 text-sm text-warning">{t("run.noOptions")}</p>}
    </form>
  );
}

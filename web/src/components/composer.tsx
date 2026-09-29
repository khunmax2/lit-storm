// The research composer: a tray of choices around a white box for the topic,
// the model beside the send button — the layout agent apps have settled on. Used on the home page (with
// a project picker) and at the foot of a topic (to research it again).
import { useQuery } from "@tanstack/react-query";
import { Gauge, Globe, Loader2, Search, SendHorizontal, Sparkles, Timer } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { api, call } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

export type Depth = "fast" | "standard" | "deep";
const DEPTHS: Depth[] = ["fast", "standard", "deep"];
export type RunForm = { topic: string; language: string; llm_model_id: string; search_provider_id: string; depth: Depth };

// One press of Start is one Run: the same key goes with every retry of the
// request, and a new key is made only after the Run was created.
export function useRequestKey() {
  const key = useRef(crypto.randomUUID());
  return { current: () => key.current, next: () => (key.current = crypto.randomUUID()) };
}

export function runBody(form: RunForm, request_key: string) {
  return {
    topic: form.topic.trim(),
    language: form.language,
    llm_model_id: form.llm_model_id || null,
    search_provider_id: form.search_provider_id || null,
    depth: form.depth,
    request_key,
  };
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

  useEffect(() => {
    // Preselect the defaults once options arrive (design: หน้าเริ่มวิจัยเลือก default ไว้ให้).
    if (!o) return;
    const model = form.llm_model_id || o.models.find((m) => m.is_default)?.id || o.models[0]?.id || "";
    const search =
      form.search_provider_id || o.search_providers.find((p) => p.is_default)?.id || o.search_providers[0]?.id || "";
    if (model !== form.llm_model_id || search !== form.search_provider_id)
      setForm({ ...form, llm_model_id: model, search_provider_id: search });
  }, [o]); // eslint-disable-line react-hooks/exhaustive-deps

  const unavailable = o && (o.models.length === 0 || o.search_providers.length === 0);
  // The level's time target, as the Administrator set it.
  const target = o?.depth_levels.find((d) => d.id === form.depth)?.target_minutes ?? 5;
  const ready = form.topic.trim().length >= 3 && !unavailable && !pending && !locked;

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
        {o && o.search_providers.length > 0 && (
          <Chip
            label={t("run.search")}
            icon={<Search className="size-3.5" />}
            value={form.search_provider_id}
            onChange={(search_provider_id) => setForm({ ...form, search_provider_id })}
            items={o.search_providers.map((p) => ({ value: p.id, label: p.label }))}
          />
        )}
        <Chip
          label={t("depth.label")}
          icon={<Gauge className="size-3.5" />}
          value={form.depth}
          onChange={(depth) => setForm({ ...form, depth: depth as Depth })}
          items={DEPTHS.map((d) => ({ value: d, label: t(`depth.${d}`) }))}
        />
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
        <div className="flex items-center gap-2 px-3 pt-2 pb-3">
          {o && o.models.length > 0 && (
            <Chip
              label={t("run.model")}
              icon={<Sparkles className="size-3.5 text-brand" />}
              value={form.llm_model_id}
              onChange={(llm_model_id) => setForm({ ...form, llm_model_id })}
              items={o.models.map((m) => ({ value: m.id, label: m.label }))}
            />
          )}
          <div className="ml-auto flex items-center gap-3">
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

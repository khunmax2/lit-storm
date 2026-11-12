// Home: the research mode as tabs and one question in the middle; recent
// research is in the sidebar.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { useState } from "react";

import { api, call } from "@/api/client";
import { ErrorText, timeAgo } from "@/components/common";
import { Composer, QuotaLine, startResearch, useRequestKey, useRunOptions, type RunForm } from "@/components/composer";
import { useOpenIssues } from "@/components/system-status";
import { Segmented } from "@/components/segmented";
import { has, useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

const ACTIVE = new Set(["running", "queued", "cancelling"]);

/** What a research mode is good at, shown when the pointer rests on its tab:
 *  its name, what stands out, and what it suits. Nothing for a mode whose
 *  words are not written yet. */
function ModeHint({ id, label }: { id: string; label: string }) {
  const { t } = useT();
  const key = `mode.tip.${id}`;
  if (!has(key)) return null;
  const fit = `${key}.fit`;
  return (
    <span className="grid gap-1.5">
      <span className="text-[13px] font-semibold">{label}</span>
      <span className="grid gap-1">
        {t(key as Key)
          .split("\n")
          .map((line) => (
            <span key={line} className="flex gap-1.5 leading-snug opacity-90">
              <span aria-hidden className="opacity-60">•</span>
              {line}
            </span>
          ))}
      </span>
      {has(fit) && (
        <span className="mt-0.5 border-t border-background/20 pt-1.5 leading-snug">
          <span className="opacity-60">{t("mode.tip.fit")}: </span>
          {t(fit as Key)}
        </span>
      )}
    </span>
  );
}

// For an Administrator: the system has failures nobody has looked at yet (server: monitor.badge).
function IssuesNotice() {
  const { t, lang } = useT();
  const me = useQuery({ queryKey: ["me"], queryFn: () => call(api.GET("/api/me")), retry: false });
  const issues = useOpenIssues(me.data?.role === "admin");
  const open = issues.data?.open_count ?? 0;
  if (!open) return null;
  return (
    <Link
      to="/status"
      className="mt-6 flex items-center gap-3 rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm transition-colors hover:bg-destructive/10"
    >
      <AlertTriangle className="size-4 shrink-0 text-destructive" />
      <span className="flex-1">
        <span className="font-medium text-destructive">{t("home.issues", { count: open })}</span>
        {issues.data?.last_at && (
          <span className="text-muted-foreground"> · {t("monitor.last")} {timeAgo(issues.data.last_at, lang)}</span>
        )}
      </span>
      <span className="flex items-center gap-1 font-medium">
        {t("home.issuesLink")}
        <ArrowRight className="size-4" />
      </span>
    </Link>
  );
}

export function HomePage() {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () => call(api.GET("/api/sessions/recent", { params: { query: { limit: 12 } } })),
    refetchInterval: 15000,
  });
  const [form, setForm] = useState<RunForm>({
    topic: "",
    language: lang,
    llm_model_id: "",
    search_provider_id: "",
    depth: "standard",
    engine: "storm",
  });
  // The tabs are the modes that can be used today: ready Engines the
  // Administrator has not switched off (docs/web-app-design.md, แท็บโหมด).
  const engines = useRunOptions().data?.engines ?? [];
  const mode = engines.some((e) => e.id === form.engine) ? form.engine : (engines[0]?.id ?? "storm");
  const modeLead = `mode.${mode}`;
  const requestKey = useRequestKey();

  // Research from here is filed in no Project; the owner can file it later
  // (as ChatGPT, Claude and Gemini do), or start it from inside a Project.
  const start = useMutation({
    mutationFn: () => startResearch({ ...form, engine: mode }, requestKey.current()),
    onSuccess: (s) => {
      requestKey.next();
      queryClient.invalidateQueries();
      navigate({ to: "/sessions/$sessionId", params: { sessionId: s.id } });
    },
  });

  const running = recent.data?.filter((s) => s.last_status && ACTIVE.has(s.last_status)).length ?? 0;

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-5 md:px-6">
        <div className="max-w-full overflow-x-auto [scrollbar-width:none]">
          {engines.length > 1 && (
            <Segmented
              label={t("mode.label")}
              value={mode}
              onChange={(engine) => setForm({ ...form, engine })}
              options={engines.map((e) => ({ value: e.id, label: e.label, hint: <ModeHint id={e.id} label={e.label} /> }))}
            />
          )}
        </div>
        <div
          className={cn(
            "flex h-9 items-center gap-2 rounded-lg border px-3 text-sm",
            running
              ? "border-success/40 bg-success-soft text-success"
              : "text-muted-foreground",
          )}
        >
          <span className={cn("size-2 rounded-full", running ? "animate-pulse bg-success" : "bg-muted-foreground/40")} />
          {t("home.running")}
          <span className={cn("rounded-md px-1.5 text-xs", running ? "bg-success/15" : "bg-muted")}>{running}</span>
        </div>
      </div>

      {/* The question sits a little above the middle of the page: recent research is in the sidebar. */}
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 pt-6 pb-[14vh]">
        <IssuesNotice />
        <div className="flex flex-col items-center pb-8 text-center">
          <h1 className="font-display text-4xl leading-tight tracking-tight text-balance md:text-6xl">
            {t("home.title")}
          </h1>
          {has(modeLead) && (
            <p className="mt-3 max-w-xl text-balance text-muted-foreground">{t(modeLead as Key)}</p>
          )}
        </div>

        <Composer
          form={{ ...form, engine: mode }}
          setForm={setForm}
          onSubmit={() => start.mutate()}
          pending={start.isPending}
          autoFocus
        />
        <div className="mt-3 flex justify-center">
          <QuotaLine />
        </div>
        {start.error && (
          <div className="mt-4">
            <ErrorText error={start.error} />
          </div>
        )}

      </div>
    </div>
  );
}

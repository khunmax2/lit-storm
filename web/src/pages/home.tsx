// Home: the research mode as tabs, one question in the middle, shortcuts and
// recent research under it.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, History, FolderOpen, Sparkles } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { api, call } from "@/api/client";
import { DOT } from "@/components/app-sidebar";
import { ErrorText, timeAgo } from "@/components/common";
import { CHIP, Composer, QuotaLine, runBody, useRequestKey, type RunForm } from "@/components/composer";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

const NEW = "__new__";

// The research engines. Only STORM runs in the first release; the others are
// the second release's (docs/web-app-implementation-plan.md, ก่อนเริ่มรุ่นสอง).
const MODES = [
  { id: "storm", label: "STORM", ready: true },
  { id: "co-storm", label: "Co-STORM", ready: false },
  { id: "deep", label: "Deep Research", ready: false },
  { id: "agent", label: "Agent Research", ready: false },
] as const;
type Mode = (typeof MODES)[number]["id"];

const ACTIVE = new Set(["running", "queued", "cancelling"]);

function Shortcut({ to, art, title, action }: { to: string; art: ReactNode; title: string; action: string }) {
  return (
    <Link
      to={to}
      className="group overflow-hidden rounded-xl border bg-card shadow-xs transition-shadow hover:shadow-md"
    >
      <div className="flex items-center gap-3 px-4 py-4">
        <div className="flex h-8 w-11 shrink-0 items-center">{art}</div>
        <span className="truncate font-medium">{title}</span>
      </div>
      <div className="flex items-center justify-between border-t bg-muted/50 px-4 py-2.5 text-sm text-muted-foreground transition-colors group-hover:text-foreground">
        {action}
        <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

// Small flat drawings for the shortcut cards, in the reference's spirit.
const ART = {
  projects: (
    <div className="relative h-7 w-10">
      <div className="absolute top-2 left-0 h-5 w-10 rounded-sm bg-amber-100 dark:bg-amber-200/30" />
      <div className="absolute top-1 left-0 h-2.5 w-10 rounded-sm bg-amber-200 dark:bg-amber-300/50" />
      <Sparkles className="absolute -top-1.5 -left-1 size-3.5 fill-amber-400 text-amber-400" />
    </div>
  ),
  report: (
    <div className="flex h-7 w-10 flex-col gap-1">
      <div className="h-3.5 rounded-sm bg-sky-400" />
      <div className="h-1 w-8 rounded-full bg-sky-200 dark:bg-sky-300/40" />
      <div className="h-1 w-6 rounded-full bg-sky-200 dark:bg-sky-300/40" />
    </div>
  ),
  trash: (
    <div className="flex h-7 w-10 flex-col justify-center gap-1.5">
      <div className="h-2 w-6 rounded-sm bg-indigo-500" />
      <div className="ml-3 h-2 w-7 rounded-sm bg-indigo-300 dark:bg-indigo-400/60" />
    </div>
  ),
};

export function HomePage() {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => call(api.GET("/api/projects")) });
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () => call(api.GET("/api/sessions/recent", { params: { query: { limit: 12 } } })),
    refetchInterval: 15000,
  });
  const [mode, setMode] = useState<Mode>("storm");
  const [form, setForm] = useState<RunForm>({ topic: "", language: lang, llm_model_id: "", search_provider_id: "" });
  const [projectId, setProjectId] = useState("");
  const requestKey = useRequestKey();

  useEffect(() => {
    if (!projectId && projects.data) setProjectId(projects.data[0]?.id ?? NEW);
  }, [projects.data, projectId]);

  const start = useMutation({
    mutationFn: async () => {
      let id = projectId;
      if (!id || id === NEW) {
        const created = await call(api.POST("/api/projects", { body: { name: t("home.defaultProject") } }));
        id = created.id;
      }
      return call(
        api.POST("/api/projects/{project_id}/sessions", {
          params: { path: { project_id: id } },
          body: runBody(form, requestKey.current()),
        }),
      );
    },
    onSuccess: (s) => {
      requestKey.next();
      queryClient.invalidateQueries();
      navigate({ to: "/sessions/$sessionId", params: { sessionId: s.id } });
    },
  });

  const current = MODES.find((m) => m.id === mode)!;
  const running = recent.data?.filter((s) => s.last_status && ACTIVE.has(s.last_status)).length ?? 0;
  const latestDone = recent.data?.find((s) => s.last_status === "succeeded");

  const projectPicker = (
    <Select value={projectId} onValueChange={setProjectId}>
      <SelectTrigger size="sm" aria-label={t("home.project")} className={cn(CHIP, "max-w-52")}>
        <FolderOpen className="size-3.5" />
        <SelectValue placeholder={t("home.project")} />
      </SelectTrigger>
      <SelectContent>
        {projects.data?.map((p) => (
          <SelectItem key={p.id} value={p.id}>
            {p.name}
          </SelectItem>
        ))}
        <SelectItem value={NEW}>
          {projects.data?.length ? t("home.newProject") : t("home.defaultProject")}
        </SelectItem>
      </SelectContent>
    </Select>
  );

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-5 md:px-6">
        <Tabs
          value={mode}
          onValueChange={(v) => setMode(v as Mode)}
          className="max-w-full overflow-x-auto [scrollbar-width:none]"
        >
          <TabsList className="h-10 rounded-xl p-1">
            {MODES.map((m) => (
              <TabsTrigger
                key={m.id}
                value={m.id}
                className="h-8 rounded-lg px-3.5 data-[state=active]:shadow-sm"
              >
                {m.label}
                {!m.ready && <span className="size-1.5 rounded-full bg-muted-foreground/40" aria-hidden />}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
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

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pb-16">
        <div className="flex flex-col items-center pt-[9vh] pb-8 text-center">
          <h1 className="font-display text-4xl leading-tight tracking-tight text-balance md:text-6xl">
            {t("home.title")}
          </h1>
          <p className="mt-3 max-w-xl text-balance text-muted-foreground">{t(`mode.${mode}`)}</p>
        </div>

        <Composer
          form={form}
          setForm={setForm}
          onSubmit={() => start.mutate()}
          pending={start.isPending}
          extra={projectPicker}
          locked={current.ready ? undefined : t("mode.soon")}
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

        <div className="mt-10 grid gap-3 sm:grid-cols-3">
          <Shortcut
            to="/projects"
            art={ART.projects}
            title={t("home.cardProjects")}
            action={t("home.cardProjectsAction", { n: projects.data?.length ?? 0 })}
          />
          <Shortcut
            to={latestDone ? `/sessions/${latestDone.id}` : "/projects"}
            art={ART.report}
            title={t("home.cardReport")}
            action={latestDone ? t("home.cardReportAction") : t("home.cardReportNone")}
          />
          <Shortcut to="/trash" art={ART.trash} title={t("nav.trash")} action={t("home.cardTrashAction")} />
        </div>

        <section className="mt-10">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-medium">
            <History className="size-4 text-muted-foreground" />
            {t("home.recentReports")}
          </h2>
          {recent.isLoading && (
            <div className="space-y-2 pl-6">
              {Array.from({ length: 3 }, (_, i) => (
                <Skeleton key={i} className="h-6" />
              ))}
            </div>
          )}
          {recent.data?.length === 0 && <p className="pl-6 text-sm text-muted-foreground">{t("projects.empty")}</p>}
          {!!recent.data?.length && (
            <ul className="ml-2 border-l pl-4">
              {recent.data.slice(0, 5).map((s) => (
                <li key={s.id}>
                  <Link
                    to="/sessions/$sessionId"
                    params={{ sessionId: s.id }}
                    className="flex items-center gap-3 rounded-md px-2 py-2.5 text-sm transition-colors hover:bg-muted/60"
                  >
                    <span
                      className={cn("size-1.5 shrink-0 rounded-full", DOT[s.last_status ?? ""] ?? "bg-muted-foreground/40")}
                    />
                    <span className="truncate">{s.title}</span>
                    <span className="hidden truncate text-xs text-muted-foreground sm:inline">· {s.project_name}</span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">{timeAgo(s.updated_at, lang)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {!!recent.data?.length && (
            <Link to="/projects" className="mt-2 ml-8 inline-block text-sm font-medium hover:underline">
              {t("home.seeMore")}
            </Link>
          )}
        </section>
      </div>
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { api, call, type Schemas } from "../api/client";
import { Button, Card, ErrorText, Field, Input, PageTitle, Select, Spinner, StatusBadge, formatDate } from "../components/ui";
import { has, useT } from "../i18n";

type Run = Schemas["RunOut"];
const FINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

// --- Projects ---------------------------------------------------------------

export function ProjectsPage() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => call(api.GET("/api/projects")) });
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => call(api.POST("/api/projects", { body: { name } })),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  return (
    <>
      <PageTitle>{t("projects.title")}</PageTitle>
      <form
        className="mb-8 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Input
          className="max-w-md flex-1"
          placeholder={t("projects.namePlaceholder")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Button disabled={create.isPending}>{t("projects.new")}</Button>
      </form>
      {projects.isLoading && <Spinner />}
      {projects.data?.length === 0 && <p className="text-muted">{t("projects.empty")}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.data?.map((p) => (
          <Link
            key={p.id}
            to="/projects/$projectId"
            params={{ projectId: p.id }}
            className="rounded-lg border border-line bg-surface p-4 transition hover:border-accent"
          >
            <div className="font-medium">{p.name}</div>
            <div className="mt-1 text-xs text-muted">{formatDate(p.created_at, lang)}</div>
          </Link>
        ))}
      </div>
    </>
  );
}

// --- the form that starts a Run ----------------------------------------------

type RunForm = { topic: string; language: string; llm_model_id: string; search_provider_id: string };

function useRunOptions() {
  return useQuery({ queryKey: ["options"], queryFn: () => call(api.GET("/api/options")) });
}

function RunFields({ form, setForm }: { form: RunForm; setForm: (f: RunForm) => void }) {
  const { t } = useT();
  const options = useRunOptions();
  const o = options.data;
  useEffect(() => {
    // Preselect the defaults once options arrive (design: หน้าเริ่มวิจัยเลือก default ไว้ให้).
    if (!o) return;
    const model = form.llm_model_id || o.models.find((m) => m.is_default)?.id || o.models[0]?.id || "";
    const search =
      form.search_provider_id || o.search_providers.find((p) => p.is_default)?.id || o.search_providers[0]?.id || "";
    if (model !== form.llm_model_id || search !== form.search_provider_id)
      setForm({ ...form, llm_model_id: model, search_provider_id: search });
  }, [o]); // eslint-disable-line react-hooks/exhaustive-deps

  if (o && (o.models.length === 0 || o.search_providers.length === 0))
    return <p className="text-sm text-warn">{t("run.noOptions")}</p>;
  return (
    <div className="flex flex-col gap-4">
      <Field label={t("run.topic")}>
        <Input
          placeholder={t("run.topicPlaceholder")}
          value={form.topic}
          onChange={(e) => setForm({ ...form, topic: e.target.value })}
          minLength={3}
          maxLength={500}
          required
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t("run.language")}>
          <Select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
            <option value="th">{t("lang.th")}</option>
            <option value="en">{t("lang.en")}</option>
          </Select>
        </Field>
        <Field label={t("run.model")}>
          <Select value={form.llm_model_id} onChange={(e) => setForm({ ...form, llm_model_id: e.target.value })}>
            {o?.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("run.search")}>
          <Select value={form.search_provider_id} onChange={(e) => setForm({ ...form, search_provider_id: e.target.value })}>
            {o?.search_providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </div>
  );
}

function body(form: RunForm) {
  return {
    topic: form.topic,
    language: form.language,
    llm_model_id: form.llm_model_id || null,
    search_provider_id: form.search_provider_id || null,
  };
}

// --- a Project and its Sessions ---------------------------------------------------

export function ProjectPage() {
  const { t, lang } = useT();
  const { projectId } = useParams({ from: "/app/projects/$projectId" });
  const navigate = useNavigate();
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => call(api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });
  const [form, setForm] = useState<RunForm>({ topic: "", language: lang, llm_model_id: "", search_provider_id: "" });
  const start = useMutation({
    mutationFn: () =>
      call(api.POST("/api/projects/{project_id}/sessions", { params: { path: { project_id: projectId } }, body: body(form) })),
    onSuccess: (s) => navigate({ to: "/sessions/$sessionId", params: { sessionId: s.id } }),
  });
  if (project.isLoading) return <Spinner />;
  if (!project.data) return <ErrorText error={project.error} />;
  return (
    <>
      <Link to="/" className="text-sm text-muted hover:text-ink">
        ← {t("nav.projects")}
      </Link>
      <PageTitle>{project.data.name}</PageTitle>
      <Card className="mb-8">
        <h2 className="mb-4 font-semibold">{t("project.newSession")}</h2>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            start.mutate();
          }}
        >
          <RunFields form={form} setForm={setForm} />
          <ErrorText error={start.error} />
          <div>
            <Button disabled={start.isPending}>{t("run.start")}</Button>
          </div>
        </form>
      </Card>
      <h2 className="mb-3 font-semibold">{t("project.sessions")}</h2>
      {project.data.sessions.length === 0 && <p className="text-muted">{t("project.empty")}</p>}
      <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
        {project.data.sessions.map((s) => (
          <li key={s.id}>
            <Link
              to="/sessions/$sessionId"
              params={{ sessionId: s.id }}
              className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-sunk"
            >
              <span className="min-w-0 truncate">{s.title}</span>
              <span className="flex shrink-0 items-center gap-3">
                <span className="hidden text-xs text-muted sm:inline">{formatDate(s.created_at, lang)}</span>
                {s.last_status && <StatusBadge status={s.last_status} />}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}

// --- a Session: its Runs, live progress, and "research again" ----------------------

function RunProgress({ run }: { run: Run }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<Schemas["EventOut"][]>([]);
  const after = events.length ? events[events.length - 1].id : 0;
  const live = !FINAL.has(run.status);
  const detail = useQuery({
    queryKey: ["run", run.id, after],
    queryFn: () =>
      call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: run.id }, query: { after } } })),
    refetchInterval: live ? 2500 : false,
  });
  useEffect(() => {
    const d = detail.data;
    if (!d) return;
    if (d.events.length) setEvents((prev) => [...prev, ...d.events]);
    if (d.status !== run.status || d.stage !== run.stage)
      queryClient.invalidateQueries({ queryKey: ["session", run.session_id] });
  }, [detail.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const browsed = useMemo(
    () => new Set(events.flatMap((e) => (e.type === "note" && e.data.kind === "browsed" ? (e.data.urls as string[]) : []))),
    [events],
  );
  const perspectives = events.find((e) => e.type === "note" && e.data.kind === "perspectives")?.data
    .perspectives as string[] | undefined;
  const stages = ["research", "outline", "article", "polish"];
  const current = stages.indexOf(run.stage ?? "");

  if (!live) return null;
  return (
    <div className="mt-4 rounded-md bg-sunk p-4 text-sm">
      <ol className="mb-3 flex flex-wrap gap-x-5 gap-y-2">
        {stages.map((s, i) => (
          <li key={s} className={i < current ? "text-ok" : i === current ? "font-medium text-accent" : "text-muted"}>
            {i < current ? "✓ " : i === current ? "● " : "○ "}
            {has(`stage.${s}`) ? t(`stage.${s}` as "stage.research") : s}
          </li>
        ))}
      </ol>
      {browsed.size > 0 && <p className="text-muted">{t("run.browsed", { n: browsed.size })}</p>}
      {perspectives && (
        <details className="mt-2 text-muted">
          <summary className="cursor-pointer">{t("run.perspectives")}</summary>
          <ul className="mt-1 list-disc pl-5">
            {perspectives.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="mt-2 text-xs text-muted">{t("run.closeSafe")}</p>
    </div>
  );
}

function RunCard({ run }: { run: Run }) {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => call(api.POST("/api/runs/{run_id}/cancel", { params: { path: { run_id: run.id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session", run.session_id] }),
  });
  const reasonKey = `reason.${run.reason}`;
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={run.status} />
            <span className="text-xs text-muted">{formatDate(run.queued_at, lang)}</span>
          </div>
          <p className="mt-2 font-medium">{run.topic}</p>
          <p className="mt-1 text-xs text-muted">
            {run.language === "th" ? t("lang.th") : t("lang.en")} · {run.model_label} · {run.search_label}
            {run.source_count != null && ` · ${t("run.sources", { n: run.source_count })}`}
          </p>
          {run.status !== "succeeded" && run.reason && run.reason !== "cancelled" && (
            <p className="mt-2 text-sm text-bad">
              {has(reasonKey) ? t(reasonKey as "reason.timed_out") : run.reason}
              {run.quota_refunded && <span className="ml-2 text-xs text-muted">({t("run.refunded")})</span>}
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {(run.status === "succeeded" || (run.status === "cancelled" && run.report_title)) && (
            <Link to="/runs/$runId" params={{ runId: run.id }}>
              <Button>{t("run.open")}</Button>
            </Link>
          )}
          {!FINAL.has(run.status) && run.status !== "cancelling" && (
            <Button
              variant="danger"
              disabled={cancel.isPending}
              onClick={() => confirm(t("run.cancelConfirm")) && cancel.mutate()}
            >
              {t("run.cancel")}
            </Button>
          )}
        </div>
      </div>
      <RunProgress run={run} />
    </Card>
  );
}

export function SessionPage() {
  const { t } = useT();
  const { sessionId } = useParams({ from: "/app/sessions/$sessionId" });
  const queryClient = useQueryClient();
  const session = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => call(api.GET("/api/sessions/{session_id}", { params: { path: { session_id: sessionId } } })),
    refetchInterval: (q) => (q.state.data?.runs.some((r) => !FINAL.has(r.status)) ? 5000 : false),
  });
  const latest = session.data?.runs[0];
  const [form, setForm] = useState<RunForm | null>(null);
  useEffect(() => {
    if (latest && !form)
      setForm({ topic: latest.topic, language: latest.language, llm_model_id: "", search_provider_id: "" });
  }, [latest]); // eslint-disable-line react-hooks/exhaustive-deps
  const again = useMutation({
    mutationFn: () =>
      call(api.POST("/api/sessions/{session_id}/runs", { params: { path: { session_id: sessionId } }, body: body(form!) })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session", sessionId] }),
  });
  if (session.isLoading) return <Spinner />;
  if (!session.data) return <ErrorText error={session.error} />;
  return (
    <>
      <Link to="/projects/$projectId" params={{ projectId: session.data.project_id }} className="text-sm text-muted hover:text-ink">
        ← {t("back")}
      </Link>
      <PageTitle>{session.data.title}</PageTitle>
      <h2 className="mb-3 font-semibold">{t("run.history")}</h2>
      <div className="mb-10 flex flex-col gap-3">
        {session.data.runs.map((r) => (
          <RunCard key={r.id} run={r} />
        ))}
      </div>
      {form && (
        <Card>
          <h2 className="mb-1 font-semibold">{t("run.again")}</h2>
          <p className="mb-4 text-sm text-muted">{t("run.againLead")}</p>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              again.mutate();
            }}
          >
            <RunFields form={form} setForm={setForm} />
            <ErrorText error={again.error} />
            <div>
              <Button disabled={again.isPending}>{t("run.start")}</Button>
            </div>
          </form>
        </Card>
      )}
    </>
  );
}

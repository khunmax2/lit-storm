import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import {
  BookOpen,
  FileText,
  FolderInput,
  FolderOpen,
  FolderPlus,
  Gauge,
  Globe,
  MoreHorizontal,
  RotateCcw,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import {
  ErrorText,
  LoadingRows,
  PageHeader,
  StatusBadge,
  Toolbar,
  domainOf,
  errorMessage,
  formatDate,
  timeAgo,
} from "@/components/common";
import { MoveSessionDialog } from "@/components/move-session";
import { FINAL, RunNotes, Stepper, useConfirm } from "@/components/run-parts";
import { Segmented } from "@/components/segmented";
import {
  Composer,
  QuotaLine,
  runBody,
  startResearch,
  useRequestKey,
  useRunOptions,
  type Depth,
  type RunForm,
} from "@/components/composer";
import { DiscussionPage } from "@/pages/discussion";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { has, useT } from "@/i18n";

type Run = Schemas["RunOut"];

// --- Projects ------------------------------------------------------------------

function NewProjectDialog() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => call(api.POST("/api/projects", { body: { name } })),
    onSuccess: (p) => {
      setOpen(false);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate({ to: "/projects/$projectId", params: { projectId: p.id } });
    },
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <FolderPlus />
          {t("projects.new")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="grid gap-4"
        >
          <DialogHeader>
            <DialogTitle>{t("projects.newTitle")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="project-name">{t("projects.name")}</Label>
            <Input
              id="project-name"
              autoFocus
              placeholder={t("projects.namePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          {create.error && <ErrorText error={create.error} />}
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {t("create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ProjectsPage() {
  const { t, lang } = useT();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => call(api.GET("/api/projects")) });
  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <Toolbar>
        <span className="text-sm font-medium">{t("projects.title")}</span>
      </Toolbar>
      <PageHeader title={t("projects.title")} actions={<NewProjectDialog />} />
      {projects.isLoading && <LoadingRows />}
      {projects.data?.length === 0 && (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FolderOpen />
            </EmptyMedia>
            <EmptyTitle>{t("projects.title")}</EmptyTitle>
            <EmptyDescription>{t("projects.empty")}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <NewProjectDialog />
          </EmptyContent>
        </Empty>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.data?.map((p) => (
          <Link key={p.id} to="/projects/$projectId" params={{ projectId: p.id }} className="group">
            <Card className="h-full py-0 transition-colors group-hover:bg-muted/40">
              <CardContent className="flex items-start gap-3 p-4">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <FolderOpen className="size-4 text-muted-foreground" />
                </div>
                <div className="min-w-0">
                  <div className="truncate font-medium">{p.name}</div>
                  <div className="text-xs text-muted-foreground">{formatDate(p.created_at, lang)}</div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

// --- a Project ------------------------------------------------------------------

export function ProjectPage() {
  const { t, lang } = useT();
  const { projectId } = useParams({ from: "/app/projects/$projectId" });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { confirm, dialog } = useConfirm();
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => call(api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });
  const [form, setForm] = useState<RunForm>({
    topic: "",
    language: lang,
    llm_model_id: "",
    search_provider_id: "",
    depth: "standard",
    engine: "storm",
  });
  const [moving, setMoving] = useState<{ id: string; title: string; project_id: string } | null>(null);
  const requestKey = useRequestKey();
  const start = useMutation({
    mutationFn: () => startResearch(form, requestKey.current(), projectId),
    onSuccess: (s) => {
      requestKey.next();
      queryClient.invalidateQueries();
      navigate({ to: "/sessions/$sessionId", params: { sessionId: s.id } });
    },
  });
  const remove = useMutation({
    mutationFn: () => call(api.DELETE("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
    onSuccess: () => {
      toast.success(t("common.deleted"));
      queryClient.invalidateQueries();
      navigate({ to: "/projects" });
    },
  });
  if (project.isLoading)
    return (
      <div className="p-8">
        <LoadingRows />
      </div>
    );
  if (!project.data)
    return (
      <div className="p-8">
        <ErrorText error={project.error} />
      </div>
    );
  const p = project.data;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      {dialog}
      <MoveSessionDialog session={moving} onOpenChange={(open) => !open && setMoving(null)} />
      <Toolbar>
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/projects">{t("projects.title")}</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="max-w-60 truncate">{p.name}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </Toolbar>
      <PageHeader
        title={p.name}
        description={t("projects.count", { n: p.sessions.length })}
        actions={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" aria-label={t("run.more")}>
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                variant="destructive"
                onClick={() => confirm(t("delete.confirmProject"), () => remove.mutate())}
              >
                <Trash2 />
                {t("delete.project")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
      />
      <Composer form={form} setForm={setForm} onSubmit={() => start.mutate()} pending={start.isPending} size="md" />
      <div className="mt-2 flex justify-end">
        <QuotaLine />
      </div>
      {start.error && (
        <div className="mt-3">
          <ErrorText error={start.error} />
        </div>
      )}

      <h2 className="mt-10 mb-3 text-sm font-medium text-muted-foreground">{t("project.sessions")}</h2>
      {p.sessions.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("project.empty")}</p>
      ) : (
        <Card className="py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">{t("run.topic")}</TableHead>
                <TableHead className="w-44">{t("common.status")}</TableHead>
                <TableHead className="w-36 text-right">{t("common.created")}</TableHead>
                <TableHead className="w-12 pr-4" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {p.sessions.map((s) => (
                <TableRow
                  key={s.id}
                  className="cursor-pointer"
                  onClick={() => navigate({ to: "/sessions/$sessionId", params: { sessionId: s.id } })}
                >
                  <TableCell className="max-w-0 pl-4">
                    <div className="truncate font-medium">{s.title}</div>
                  </TableCell>
                  <TableCell>{s.last_status && <StatusBadge status={s.last_status} />}</TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {timeAgo(s.created_at, lang)}
                  </TableCell>
                  <TableCell className="pr-4 text-right" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      aria-label={t("move.title")}
                      onClick={() => setMoving({ id: s.id, title: s.title, project_id: p.id })}
                    >
                      <FolderInput />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

// --- all research ---------------------------------------------------------------------

type Listed = Schemas["RecentSession"];

/** Every topic, filed or not, like ChatGPT's and Perplexity's library. */
export function AllResearchPage() {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { confirm, dialog } = useConfirm();
  const all = useQuery({ queryKey: ["sessions"], queryFn: () => call(api.GET("/api/sessions")) });
  const [unfiledOnly, setUnfiledOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [moving, setMoving] = useState<Listed | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => call(api.DELETE("/api/sessions/{session_id}", { params: { path: { session_id: id } } })),
    onSuccess: () => {
      toast.success(t("common.deleted"));
      queryClient.invalidateQueries();
    },
    onError: (e) => toast.error(errorMessage(e, t)),
  });
  const q = query.trim().toLowerCase();
  const rows = (all.data ?? []).filter(
    (s) =>
      (!unfiledOnly || !s.project_id) &&
      (!q || s.title.toLowerCase().includes(q) || (s.project_name ?? "").toLowerCase().includes(q)),
  );

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      {dialog}
      <MoveSessionDialog session={moving} onOpenChange={(open) => !open && setMoving(null)} />
      <Toolbar>
        <span className="text-sm font-medium">{t("nav.allResearch")}</span>
      </Toolbar>
      <PageHeader title={t("nav.allResearch")} description={t("all.lead")} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("search.placeholder")}
          className="h-9 max-w-xs"
        />
        <Segmented
          label={t("home.project")}
          value={unfiledOnly ? "unfiled" : "all"}
          onChange={(v) => setUnfiledOnly(v === "unfiled")}
          options={[
            { value: "all", label: t("all.every") },
            { value: "unfiled", label: t("move.none") },
          ]}
        />
      </div>
      {all.isLoading && <LoadingRows />}
      {all.data && rows.length === 0 && (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BookOpen />
            </EmptyMedia>
            <EmptyDescription>{all.data.length ? t("search.empty") : t("projects.empty")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
      {rows.length > 0 && (
        <Card className="py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">{t("run.topic")}</TableHead>
                <TableHead className="w-48">{t("home.project")}</TableHead>
                <TableHead className="w-36">{t("common.status")}</TableHead>
                <TableHead className="w-32 text-right">{t("all.updated")}</TableHead>
                <TableHead className="w-12 pr-4" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((s) => (
                <TableRow
                  key={s.id}
                  className="cursor-pointer"
                  onClick={() => navigate({ to: "/sessions/$sessionId", params: { sessionId: s.id } })}
                >
                  <TableCell className="max-w-0 pl-4">
                    <div className="truncate font-medium">{s.title}</div>
                  </TableCell>
                  <TableCell className="max-w-0">
                    <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                      <FolderOpen className="size-3.5 shrink-0" />
                      <span className="truncate">{s.project_name ?? "—"}</span>
                    </span>
                  </TableCell>
                  <TableCell>{s.last_status && <StatusBadge status={s.last_status} />}</TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {timeAgo(s.updated_at, lang)}
                  </TableCell>
                  <TableCell className="pr-4 text-right" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8" aria-label={t("run.more")}>
                          <MoreHorizontal />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setMoving(s)}>
                          <FolderInput />
                          {t("move.title")}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="destructive"
                          onClick={() => confirm(t("delete.confirmSession"), () => remove.mutate(s.id))}
                        >
                          <Trash2 />
                          {t("delete.session")}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

// --- a Run --------------------------------------------------------------------------

function LiveProgress({ run }: { run: Run }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<Schemas["EventOut"][]>([]);
  const after = events.length ? events[events.length - 1].id : 0;
  const live = run.status === "running" || run.status === "cancelling";
  const detail = useQuery({
    queryKey: ["run", run.id, after],
    queryFn: () => call(api.GET("/api/runs/{run_id}", { params: { path: { run_id: run.id }, query: { after } } })),
    refetchInterval: live ? 2500 : false,
    enabled: live,
  });
  useEffect(() => {
    const d = detail.data;
    if (!d) return;
    if (d.events.length) setEvents((prev) => [...prev, ...d.events]);
    if (d.status !== run.status || d.stage !== run.stage) {
      queryClient.invalidateQueries({ queryKey: ["session", run.session_id] });
      queryClient.invalidateQueries({ queryKey: ["recent"] });
    }
  }, [detail.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const browsed = useMemo(
    () => [
      ...new Set(
        events.flatMap((e) => (e.type === "note" && e.data.kind === "browsed" ? (e.data.urls as string[]) : [])),
      ),
    ],
    [events],
  );
  if (!live) return null;
  return (
    <div className="space-y-3 rounded-xl bg-muted/50 p-4">
      <Stepper stage={run.stage} status={run.status} engine={run.engine} />
      {browsed.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Globe className="size-3.5" />
          {t("run.browsed", { n: browsed.length })}
          {browsed.slice(-4).map((u) => (
            <span key={u} className="max-w-48 truncate rounded-full bg-background px-2 py-0.5">
              {domainOf(u)}
            </span>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">{t("run.closeSafe")}</p>
    </div>
  );
}

function ChooseAgain({ run }: { run: Run }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const o = useRunOptions().data;
  const [model, setModel] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => {
    if (!o) return;
    setModel((m) => m || o.models.find((x) => x.is_default)?.id || o.models[0]?.id || "");
    setSearch((p) => p || o.search_providers.find((x) => x.is_default)?.id || o.search_providers[0]?.id || "");
  }, [o]);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/runs/{run_id}/selection", {
          params: { path: { run_id: run.id } },
          body: { llm_model_id: model, search_provider_id: search },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session", run.session_id] }),
  });
  return (
    <div className="space-y-3 rounded-xl border border-warning/30 bg-warning-soft p-4 text-sm">
      <p>{t("run.chooseAgain")}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={model} onValueChange={setModel}>
          <SelectTrigger className="w-56 bg-background">
            <SelectValue placeholder={t("run.model")} />
          </SelectTrigger>
          <SelectContent>
            {o?.models.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={search} onValueChange={setSearch}>
          <SelectTrigger className="w-44 bg-background">
            <SelectValue placeholder={t("run.search")} />
          </SelectTrigger>
          <SelectContent>
            {o?.search_providers.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button disabled={save.isPending || !model || !search} onClick={() => save.mutate()}>
          {t("run.queueAgain")}
        </Button>
      </div>
      {save.error && <ErrorText error={save.error} />}
    </div>
  );
}

function RunCard({ run, confirm }: { run: Run; confirm: (text: string, action: () => void) => void }) {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["session", run.session_id] });
    queryClient.invalidateQueries({ queryKey: ["quota"] });
    queryClient.invalidateQueries({ queryKey: ["recent"] });
  };
  const onError = (e: unknown) => toast.error(errorMessage(e, t));
  const cancel = useMutation({
    mutationFn: () => call(api.POST("/api/runs/{run_id}/cancel", { params: { path: { run_id: run.id } } })),
    onSuccess: refresh,
    onError,
  });
  const retry = useMutation({
    mutationFn: () => call(api.POST("/api/runs/{run_id}/retry", { params: { path: { run_id: run.id } } })),
    onSuccess: refresh,
    onError,
  });
  const remove = useMutation({
    mutationFn: () => call(api.DELETE("/api/runs/{run_id}", { params: { path: { run_id: run.id } } })),
    onSuccess: () => {
      toast.success(t("common.deleted"));
      refresh();
    },
    onError,
  });
  const readable = run.status === "succeeded" || (run.status === "cancelled" && !!run.report_title);
  const reasonKey = `reason.${run.reason}`;
  const canRetry = ["failed", "interrupted", "cancelled"].includes(run.status);
  const canCancel = !FINAL.has(run.status) && run.status !== "cancelling";

  return (
    <Card className="gap-4 py-4">
      <CardContent className="space-y-4 px-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <StatusBadge status={run.status} />
              <span>{formatDate(run.queued_at, lang)}</span>
              {run.parent_run_id && (
                <span className="flex items-center gap-1">
                  <RotateCcw className="size-3" />
                  {t("run.retryOf")}
                </span>
              )}
            </div>
            <div className="font-medium leading-snug">{run.report_title || run.topic}</div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="rounded-md bg-muted px-1.5 py-0.5 font-medium text-foreground/80">{run.engine_label}</span>
              <span className="flex items-center gap-1">
                <Globe className="size-3" />
                {run.language === "th" ? t("lang.th") : t("lang.en")}
              </span>
              <span className="flex items-center gap-1">
                <Sparkles className="size-3" />
                {run.model_label}
              </span>
              <span>{run.search_label}</span>
              <span className="flex items-center gap-1">
                <Gauge className="size-3" />
                {t(`depth.${run.depth as Depth}`)}
              </span>
              {run.source_count != null && (
                <span className="flex items-center gap-1">
                  <BookOpen className="size-3" />
                  {t("run.sources", { n: run.source_count })}
                </span>
              )}
            </div>
            <RunNotes notes={run.notes ?? {}} />
            {!!run.sections?.length && (
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer select-none">{t("sections.set", { n: run.sections.length })}</summary>
                <ol className="mt-1.5 list-decimal pl-7 text-foreground/80">
                  {run.sections.map((h, i) => (
                    <li key={i}>{h}</li>
                  ))}
                </ol>
              </details>
            )}
            {!!run.refinement?.length && (
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer select-none">{t("refine.answered", { n: run.refinement.length })}</summary>
                <dl className="mt-1.5 grid gap-1 pl-3">
                  {run.refinement.map((x, i) => (
                    <div key={i}>
                      <dt>{x.question}</dt>
                      <dd className="text-foreground/80">{x.answer}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {readable && (
              <Button asChild>
                <Link to="/runs/$runId" params={{ runId: run.id }}>
                  <FileText />
                  {t("run.open")}
                </Link>
              </Button>
            )}
            {canRetry && !readable && (
              <Button variant="outline" disabled={retry.isPending} onClick={() => retry.mutate()}>
                <RotateCcw />
                {t("run.retry")}
              </Button>
            )}
            {canCancel && (
              <Button
                variant="outline"
                disabled={cancel.isPending}
                onClick={() => confirm(t("run.cancelConfirm"), () => cancel.mutate())}
              >
                <Square />
                {t("run.cancel")}
              </Button>
            )}
            {FINAL.has(run.status) && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label={t("run.more")}>
                    <MoreHorizontal />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {canRetry && readable && (
                    <>
                      <DropdownMenuItem onClick={() => retry.mutate()}>
                        <RotateCcw />
                        {t("run.retry")}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => confirm(t("delete.confirmRun"), () => remove.mutate())}
                  >
                    <Trash2 />
                    {t("delete.run")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
        {run.status !== "succeeded" && run.reason && run.reason !== "cancelled" && (
          <p className="rounded-lg bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {has(reasonKey) ? t(reasonKey as "reason.timed_out") : run.reason}
            {run.quota_refunded && <span className="ml-2 text-xs text-muted-foreground">· {t("run.refunded")}</span>}
          </p>
        )}
        {run.status === "needs_selection" && <ChooseAgain run={run} />}
        {run.status === "queued" && <p className="text-xs text-muted-foreground">{t("run.closeSafe")}</p>}
        <LiveProgress run={run} />
      </CardContent>
    </Card>
  );
}

// --- a Session ------------------------------------------------------------------------

export function SessionPage() {
  const { t } = useT();
  const { sessionId } = useParams({ from: "/app/sessions/$sessionId" });
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { confirm, dialog } = useConfirm();
  const session = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => call(api.GET("/api/sessions/{session_id}", { params: { path: { session_id: sessionId } } })),
    refetchInterval: (q) => (q.state.data?.runs.some((r) => !FINAL.has(r.status)) ? 4000 : false),
  });
  const [moving, setMoving] = useState(false);
  const latest = session.data?.runs[0];
  const [form, setForm] = useState<RunForm | null>(null);
  useEffect(() => {
    if (latest && !form)
      setForm({
        topic: latest.topic,
        language: latest.language,
        llm_model_id: "",
        search_provider_id: "",
        depth: latest.depth as Depth,
        engine: latest.engine,
        sections_text: (latest.sections ?? []).join("\n"),
      });
  }, [latest]); // eslint-disable-line react-hooks/exhaustive-deps
  const requestKey = useRequestKey();
  const again = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/sessions/{session_id}/runs", {
          params: { path: { session_id: sessionId } },
          body: runBody(form!, requestKey.current()),
        }),
      ),
    onSuccess: () => {
      requestKey.next();
      queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["quota"] });
      queryClient.invalidateQueries({ queryKey: ["recent"] });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });
  const remove = useMutation({
    mutationFn: () => call(api.DELETE("/api/sessions/{session_id}", { params: { path: { session_id: sessionId } } })),
    onSuccess: () => {
      const projectId = session.data!.project_id;
      toast.success(t("common.deleted"));
      queryClient.invalidateQueries();
      if (projectId) navigate({ to: "/projects/$projectId", params: { projectId } });
      else navigate({ to: "/research" });
    },
  });
  if (session.isLoading)
    return (
      <div className="p-8">
        <LoadingRows />
      </div>
    );
  if (!session.data)
    return (
      <div className="p-8">
        <ErrorText error={session.error} />
      </div>
    );
  const s = session.data;
  // A Discussion lives at the same address and has a page of its own.
  if (s.kind === "discussion") return <DiscussionPage sessionId={s.id} />;

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      {dialog}
      <MoveSessionDialog session={moving ? s : null} onOpenChange={setMoving} />
      <Toolbar>
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:inline-flex">
              <BreadcrumbLink asChild>
                {s.project_id ? (
                  <Link to="/projects/$projectId" params={{ projectId: s.project_id }}>
                    {s.project_name}
                  </Link>
                ) : (
                  <Link to="/research">{t("nav.allResearch")}</Link>
                )}
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:inline-flex" />
            <BreadcrumbItem>
              <BreadcrumbPage className="max-w-72 truncate">{s.title}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </Toolbar>
      <PageHeader
        title={s.title}
        eyebrow={
          <button
            type="button"
            onClick={() => setMoving(true)}
            className="inline-flex items-center gap-1.5 hover:text-foreground"
          >
            <FolderOpen className="size-3.5" />
            {s.project_name ?? t("move.none")}
          </button>
        }
        actions={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" aria-label={t("run.more")}>
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setMoving(true)}>
                <FolderInput />
                {t("move.title")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onClick={() => confirm(t("delete.confirmSession"), () => remove.mutate())}
              >
                <Trash2 />
                {t("delete.session")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
      />
      <div className="space-y-3">
        {s.runs.map((r) => (
          <RunCard key={r.id} run={r} confirm={confirm} />
        ))}
      </div>
      {form && (
        <section className="mt-10 space-y-2">
          <h2 className="text-sm font-medium">{t("run.again")}</h2>
          <p className="text-sm text-muted-foreground">{t("run.againLead")}</p>
          <Composer form={form} setForm={setForm} onSubmit={() => again.mutate()} pending={again.isPending} size="md" />
          <div className="flex justify-end">
            <QuotaLine />
          </div>
          {again.error && <ErrorText error={again.error} />}
        </section>
      )}
    </div>
  );
}

// Home: one question in the middle of the page, recent research under it.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, FolderOpen } from "lucide-react";
import { useEffect, useState } from "react";

import { api, call } from "@/api/client";
import { ErrorText, StatusBadge, timeAgo } from "@/components/common";
import { Composer, QuotaLine, runBody, useRequestKey, type RunForm } from "@/components/composer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/i18n";

const NEW = "__new__";

export function HomePage() {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => call(api.GET("/api/projects")) });
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () => call(api.GET("/api/sessions/recent", { params: { query: { limit: 12 } } })),
  });
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

  const projectPicker = (
    <Select value={projectId} onValueChange={setProjectId}>
      <SelectTrigger
        size="sm"
        aria-label={t("home.project")}
        className="h-8 max-w-48 gap-1.5 rounded-full border-transparent bg-muted/60 px-3 text-xs shadow-none hover:bg-muted"
      >
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
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pb-16">
      <div className="flex flex-col items-center pt-[12vh] pb-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{t("home.title")}</h1>
        <p className="mt-3 max-w-xl text-balance text-muted-foreground">{t("home.subtitle")}</p>
      </div>
      <Composer
        form={form}
        setForm={setForm}
        onSubmit={() => start.mutate()}
        pending={start.isPending}
        extra={projectPicker}
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

      <section className="mt-16">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">{t("home.recentReports")}</h2>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/projects">
              {t("home.viewAll")}
              <ArrowRight />
            </Link>
          </Button>
        </div>
        {recent.isLoading && (
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        )}
        {recent.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("projects.empty")}</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          {recent.data?.slice(0, 6).map((s) => (
            <Link key={s.id} to="/sessions/$sessionId" params={{ sessionId: s.id }} className="group">
              <Card className="h-full py-0 transition-colors group-hover:bg-muted/40">
                <CardContent className="flex h-full flex-col gap-3 p-4">
                  <div className="line-clamp-2 font-medium leading-snug">{s.title}</div>
                  <div className="mt-auto flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <FolderOpen className="size-3.5 shrink-0" />
                      <span className="truncate">{s.project_name}</span>
                      <span>· {timeAgo(s.updated_at, lang)}</span>
                    </span>
                    {s.last_status && <StatusBadge status={s.last_status} />}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

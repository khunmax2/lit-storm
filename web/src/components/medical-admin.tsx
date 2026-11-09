// Medical Review's settings, under the research modes: where MedicalReviewerAgent is and its key
// (server: api/medical.py, docs/adr/0013). MRA's own models, sources and limits are set in its console.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, HeartPulse, Loader2, PlugZap, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import { ErrorText } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT } from "@/i18n";

function Line({ ok, children }: { ok: boolean | null | undefined; children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-1.5">
      {ok ? <CheckCircle2 className="size-4 text-success" /> : <XCircle className="size-4 text-destructive" />}
      {children}
    </li>
  );
}

export function MedicalSettings() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["admin-medical"], queryFn: () => call(api.GET("/api/admin/medical")) });
  const [form, setForm] = useState<{ url: string; web_url: string; api_key: string } | null>(null);
  const current = form ?? (settings.data ? { url: settings.data.url, web_url: settings.data.web_url, api_key: "" } : null);
  const [result, setResult] = useState<Schemas["MedicalCheck"] | null>(null);

  const check = useMutation({
    mutationFn: () => call(api.POST("/api/admin/medical/check")),
    onSuccess: setResult,
  });
  const save = useMutation({
    mutationFn: () =>
      call(api.PUT("/api/admin/medical", { body: { url: current!.url, web_url: current!.web_url, api_key: current!.api_key || null } })),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-medical"], data);
      queryClient.invalidateQueries({ queryKey: ["options"] });
      queryClient.invalidateQueries({ queryKey: ["admin-engines"] });
      setForm(null);
      toast.success(t("common.saved"));
      check.mutate();
    },
  });

  if (!current) return null;
  const set = (patch: Partial<typeof current>) => setForm({ ...current, ...patch });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HeartPulse className="size-4 text-brand" />
          {t("medical.admin.title")}
        </CardTitle>
        <CardDescription>{t("medical.admin.lead")}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="mra-url">{t("medical.admin.url")}</Label>
          <Input id="mra-url" placeholder="http://host.docker.internal:8088" value={current.url} onChange={(e) => set({ url: e.target.value })} />
          <span className="text-xs text-muted-foreground">{t("medical.admin.urlHint")}</span>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="mra-web">{t("medical.admin.webUrl")}</Label>
          <Input id="mra-web" placeholder="http://localhost:8088" value={current.web_url} onChange={(e) => set({ web_url: e.target.value })} />
          <span className="text-xs text-muted-foreground">{t("medical.admin.webUrlHint")}</span>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="mra-key">{t("medical.admin.key")}</Label>
          <Input
            id="mra-key"
            type="password"
            autoComplete="off"
            placeholder={settings.data?.has_key ? t("medical.admin.keyKept") : "mra_…"}
            value={current.api_key}
            onChange={(e) => set({ api_key: e.target.value })}
          />
          <span className="text-xs text-muted-foreground">{t("medical.admin.keyHint")}</span>
          <code className="w-fit rounded bg-muted px-2 py-0.5 text-xs">
            docker compose exec api python -m app.cli.keys mint --name DeepLit --quota 1000
          </code>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={save.isPending || !current.url.trim()} onClick={() => save.mutate()}>
            {save.isPending && <Loader2 className="animate-spin" />}
            {t("save")}
          </Button>
          <Button variant="outline" disabled={check.isPending || !settings.data?.url} onClick={() => check.mutate()}>
            {check.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
            {t("medical.admin.check")}
          </Button>
          {settings.data?.console_url && (
            <Button variant="ghost" asChild>
              <a href={settings.data.console_url} target="_blank" rel="noreferrer">
                <ExternalLink />
                {t("medical.admin.console")}
              </a>
            </Button>
          )}
        </div>
        <ErrorText error={save.error ?? check.error} />
        {result && (
          <ul className="grid gap-1 rounded-lg border bg-muted/40 p-3 text-sm">
            <Line ok={result.reachable}>{result.reachable ? t("medical.admin.reachable") : `${t("medical.admin.unreachable")} ${result.reason ?? ""}`}</Line>
            {result.reachable && (
              <Line ok={result.accepting}>{result.accepting ? t("medical.admin.accepting") : `${t("medical.admin.notAccepting")} ${result.reason ?? ""}`}</Line>
            )}
            {result.key_ok !== null && result.key_ok !== undefined && (
              <Line ok={result.key_ok}>{result.key_ok ? t("medical.admin.keyOk") : t("medical.admin.keyBad")}</Line>
            )}
            {result.sources.length > 0 && (
              <li className="text-xs text-muted-foreground">{t("medical.admin.sources", { list: result.sources.join(", ") })}</li>
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

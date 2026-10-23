// Settings › System status: what failed, grouped into Issues; how long each mode takes; the queue
// (server: litstorm.monitor). Only what the system did is shown, never a topic or a report.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCheck, CheckCircle2, Eye } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import { ErrorText, LoadingRows, PortalTo, errorMessage, formatDate, timeAgo } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

type Issue = Schemas["IssueOut"];

const WINDOWS = [1, 7, 30];

export function useSystemStatus(days = 7) {
  return useQuery({
    queryKey: ["admin-monitor", days],
    queryFn: () => call(api.GET("/api/admin/monitor", { params: { query: { days } } })),
    refetchInterval: 60_000,
  });
}

function minutes(m: number | null | undefined) {
  return m == null ? "–" : m < 10 ? m.toFixed(1) : Math.round(m).toString();
}

function useAcknowledge() {
  const { t } = useT();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keys: string[]) => call(api.POST("/api/admin/monitor/acknowledge", { body: { keys } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-monitor"] }),
    onError: (e) => toast.error(errorMessage(e, t)),
  });
}

function IssueCard({ issue }: { issue: Issue }) {
  const { t, lang } = useT();
  const acknowledge = useAcknowledge();
  return (
    <Card className={cn("gap-3 py-4", issue.open && "border-destructive/40")}>
      <CardContent className="grid gap-2 px-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {issue.open ? (
                <AlertTriangle className="size-4 shrink-0 text-destructive" />
              ) : issue.severity === "watch" ? (
                <Eye className="size-4 shrink-0 text-muted-foreground" />
              ) : (
                <CheckCircle2 className="size-4 shrink-0 text-success" />
              )}
              <span className="font-medium">{t(`monitor.reason.${issue.reason}` as Key)}</span>
              {issue.severity === "watch" && <Badge variant="secondary">{t("monitor.watch")}</Badge>}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {issue.engine_label}
              {issue.model_label && ` · ${issue.model_label}`} ·{" "}
              {t("monitor.times", { count: issue.count, users: issue.users.length })} · {t("monitor.last")}{" "}
              {timeAgo(issue.last_at, lang)}
            </div>
          </div>
          {issue.open && (
            <Button size="sm" variant="outline" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate([issue.key])}>
              <CheckCheck />
              {t("monitor.acknowledge")}
            </Button>
          )}
        </div>
        {issue.message && (
          <p className="rounded-md bg-muted/60 px-2 py-1.5 font-mono text-xs break-words">{issue.message}</p>
        )}
        <p className="text-xs">{t(`monitor.hint.${issue.reason}` as Key)}</p>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            {t("monitor.who")}: {issue.users.join(", ")}
          </summary>
          <ul className="mt-1 grid gap-0.5 pl-4">
            {issue.recent.map((o, i) => (
              <li key={i} className="list-disc">
                {formatDate(o.at, lang)} · {o.who}
              </li>
            ))}
            {issue.count > issue.recent.length && <li className="list-none">…</li>}
          </ul>
        </details>
        {!issue.open && issue.acknowledged_at && (
          <p className="text-xs text-muted-foreground">
            {t("monitor.acknowledgedAt", { at: formatDate(issue.acknowledged_at, lang) })}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function SystemStatus() {
  const { t, lang } = useT();
  const [days, setDays] = useState(7);
  const status = useSystemStatus(days);
  const acknowledge = useAcknowledge();
  if (status.isLoading) return <LoadingRows />;
  if (!status.data) return <ErrorText error={status.error} />;
  const s = status.data;
  const open = s.issues.filter((i) => i.open);
  const rest = s.issues.filter((i) => !i.open);
  const q = s.queue;

  return (
    <div className="grid gap-4">
      <PortalTo id="settings-actions">
        <div className="flex gap-2">
          <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WINDOWS.map((d) => (
                <SelectItem key={d} value={String(d)}>
                  {t("monitor.window", { days: d })}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {open.length > 1 && (
            <Button variant="outline" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(open.map((i) => i.key))}>
              <CheckCheck />
              {t("monitor.acknowledgeAll")}
            </Button>
          )}
        </div>
      </PortalTo>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="gap-1 py-4">
          <CardContent className="px-4">
            <div className="text-xs text-muted-foreground">{t("monitor.open")}</div>
            <div className={cn("text-2xl font-semibold tabular-nums", open.length && "text-destructive")}>{open.length}</div>
          </CardContent>
        </Card>
        <Card className="gap-1 py-4">
          <CardContent className="px-4">
            <div className="text-xs text-muted-foreground">{t("monitor.running")}</div>
            <div className="text-2xl font-semibold tabular-nums">
              {q.running} <span className="text-sm font-normal text-muted-foreground">/ {q.max_running}</span>
            </div>
          </CardContent>
        </Card>
        <Card className="gap-1 py-4">
          <CardContent className="px-4">
            <div className="text-xs text-muted-foreground">{t("monitor.queued")}</div>
            <div className="text-2xl font-semibold tabular-nums">{q.queued}</div>
            {q.oldest_wait_seconds != null && (
              <div className="text-xs text-muted-foreground">
                {t("monitor.oldestWait", { minutes: Math.max(1, Math.round(q.oldest_wait_seconds / 60)) })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {open.length === 0 && (
        <Card className="py-4">
          <CardContent className="flex items-center gap-2 px-4 text-sm">
            <CheckCircle2 className="size-4 text-success" />
            {t("monitor.allClear")}
          </CardContent>
        </Card>
      )}
      {open.map((i) => (
        <IssueCard key={i.key} issue={i} />
      ))}
      {rest.length > 0 && (
        <details className="grid gap-3" open={open.length === 0}>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            {t("monitor.earlier", { count: rest.length })}
          </summary>
          <div className="mt-3 grid gap-3">
            {rest.map((i) => (
              <IssueCard key={i.key} issue={i} />
            ))}
          </div>
        </details>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t("monitor.byMode")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("monitor.mode")}</TableHead>
                <TableHead className="text-right">{t("monitor.runs")}</TableHead>
                <TableHead className="text-right">{t("monitor.succeeded")}</TableHead>
                <TableHead className="text-right">{t("monitor.failed")}</TableHead>
                <TableHead className="text-right">{t("monitor.p50")}</TableHead>
                <TableHead className="text-right">{t("monitor.p90")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {s.engines.map((e) => (
                <TableRow key={e.engine}>
                  <TableCell>{e.engine_label}</TableCell>
                  <TableCell className="text-right tabular-nums">{e.runs}</TableCell>
                  <TableCell className="text-right tabular-nums">{e.succeeded}</TableCell>
                  <TableCell className={cn("text-right tabular-nums", e.failed > 0 && "text-destructive")}>{e.failed}</TableCell>
                  <TableCell className="text-right tabular-nums">{minutes(e.p50_minutes)}</TableCell>
                  <TableCell className="text-right tabular-nums">{minutes(e.p90_minutes)}</TableCell>
                </TableRow>
              ))}
              {s.engines.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground">
                    {t("monitor.noRuns")}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("monitor.since", { at: formatDate(s.since, lang) })}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

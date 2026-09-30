// Asking an Administrator for help (Support Access Grant, docs/CONTEXT.md):
// the owner names one, who may then read this Run — or this Discussion — for
// 24 hours; each read is listed here, and the grant can be revoked at once.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { api, call } from "@/api/client";
import { ErrorText, formatDate } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useT, type Key } from "@/i18n";

export function SupportDialog({
  runId,
  sessionId,
  open,
  onOpenChange,
}: {
  runId?: string;
  sessionId?: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const key = ["grants", runId ?? sessionId];
  const admins = useQuery({ queryKey: ["support-admins"], queryFn: () => call(api.GET("/api/support/admins")), enabled: open });
  const grants = useQuery({
    queryKey: key,
    queryFn: () =>
      call(api.GET("/api/grants", { params: { query: runId ? { run_id: runId } : { session_id: sessionId } } })),
    enabled: open,
  });
  const [adminId, setAdminId] = useState("");
  const grant = useMutation({
    mutationFn: () =>
      call(api.POST("/api/grants", { body: { admin_id: adminId, run_id: runId ?? null, session_id: sessionId ?? null } })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key });
      toast.success(t("support.granted"));
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => call(api.DELETE("/api/grants/{grant_id}", { params: { path: { grant_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("support.title")}</DialogTitle>
          <DialogDescription>{t("support.lead")}</DialogDescription>
        </DialogHeader>
        {admins.data?.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("support.noAdmins")}</p>
        ) : (
          <div className="flex gap-2">
            <Select value={adminId} onValueChange={setAdminId}>
              <SelectTrigger className="flex-1" aria-label={t("support.who")}>
                <SelectValue placeholder={t("support.who")} />
              </SelectTrigger>
              <SelectContent>
                {admins.data?.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name} · {a.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button disabled={!adminId || grant.isPending} onClick={() => grant.mutate()}>
              {t("support.grant")}
            </Button>
          </div>
        )}
        {grant.error && <ErrorText error={grant.error} />}
        <div className="grid max-h-80 gap-2 overflow-y-auto">
          {grants.data?.map((g) => (
            <div key={g.id} className="rounded-lg border p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-medium">{g.admin.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {g.revoked_at
                      ? t("support.revokedAt", { at: formatDate(g.revoked_at, lang) })
                      : g.live
                        ? t("support.until", { at: formatDate(g.expires_at, lang) })
                        : t("support.expired")}
                  </div>
                </div>
                {g.live ? (
                  <Button variant="outline" size="sm" disabled={revoke.isPending} onClick={() => revoke.mutate(g.id)}>
                    {t("support.revoke")}
                  </Button>
                ) : (
                  <Badge variant="secondary">{t("support.ended")}</Badge>
                )}
              </div>
              {g.accesses.length > 0 ? (
                <ul className="mt-2 grid gap-0.5 border-t pt-2 text-xs text-muted-foreground">
                  {g.accesses.map((a, i) => (
                    <li key={i}>
                      {formatDate(a.at, lang)} · {t(`support.what.${a.what}` as Key)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 border-t pt-2 text-xs text-muted-foreground">{t("support.notYet")}</p>
              )}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// A User's connections: the API tokens their AI tools and programs reach DeepLit's MCP server with
// (server: api/tokens.py, docs/adr/0009).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api, call } from "@/api/client";
import { ErrorText, LoadingRows, PageHeader } from "@/components/common";
import { useConfirm } from "@/components/run-parts";
import { NewTokenDialog, TokenTable } from "@/components/tokens";
import { McpSetup } from "@/components/mcp-setup";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n";

export function ConnectionsPage() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const { confirm, dialog } = useConfirm();
  const [making, setMaking] = useState(false);
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => call(api.GET("/api/me/connection")) });
  const tokens = useQuery({ queryKey: ["my-tokens"], queryFn: () => call(api.GET("/api/me/tokens")) });
  const revoke = useMutation({
    mutationFn: (id: string) => call(api.DELETE("/api/me/tokens/{token_id}", { params: { path: { token_id: id } } })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-tokens"] });
      toast.success(t("tokens.revoked"));
    },
  });
  const c = connection.data;
  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <PageHeader
        title={t("connections.title")}
        description={t("connections.lead")}
        actions={
          c?.may_create && (
            <Button onClick={() => setMaking(true)}>
              <Plus />
              {t("tokens.new")}
            </Button>
          )
        }
      />
      <div className="grid gap-6">
        {c && !c.enabled && (
          <Alert>
            <AlertDescription>{t("connections.off")}</AlertDescription>
          </Alert>
        )}
        {c?.enabled && !c.may_create && (
          <Alert>
            <AlertDescription>{t("connections.notAllowed")}</AlertDescription>
          </Alert>
        )}
        {c && <McpSetup endpoints={c.endpoints} />}
        <section className="grid gap-3">
          <h2 className="text-sm font-medium">{t("tokens.title")}</h2>
          {tokens.isLoading ? (
            <LoadingRows />
          ) : (
            <TokenTable
              rows={tokens.data ?? []}
              onRevoke={(r) => confirm(t("tokens.revokeConfirm", { name: r.name }), () => revoke.mutate(r.id))}
            />
          )}
          <ErrorText error={tokens.error ?? revoke.error} />
        </section>
      </div>
      <NewTokenDialog
        open={making}
        onOpenChange={(o) => {
          setMaking(o);
          if (!o) queryClient.invalidateQueries({ queryKey: ["my-tokens"] });
        }}
        make={(body) => call(api.POST("/api/me/tokens", { body }))}
        after={(made) => c && <McpSetup endpoints={c.endpoints} token={made.token} compact />}
      />
      {dialog}
    </div>
  );
}

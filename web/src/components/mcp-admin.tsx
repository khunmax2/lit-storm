// Settings › MCP: the server on or off, who may make tokens, integration accounts for other systems, and
// every token there is (server: api/tokens.py, docs/adr/0009).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Pencil, Plug, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import { ErrorText, LoadingRows, PortalTo, StatusBadge, timeAgo } from "@/components/common";
import { useRunOptions } from "@/components/composer";
import { useConfirm } from "@/components/run-parts";
import { McpSetup } from "@/components/mcp-setup";
import { NewTokenDialog, TokenTable } from "@/components/tokens";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n";

type Account = Schemas["IntegrationOut"];
type AccountForm = { name: string; quota: string; concurrent: string; engines: string[] | null };

function Toggle({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 p-3">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </label>
  );
}

const number = (v: string) => (v.trim() === "" ? null : Math.max(0, Math.round(Number(v))));

function AccountDialog({ account, open, onOpenChange }: { account: Account | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const engines = useRunOptions().data?.engines ?? [];
  const [form, setForm] = useState<AccountForm>(() => ({
    name: account?.name ?? "",
    quota: account?.monthly_run_quota?.toString() ?? "",
    concurrent: account?.max_concurrent_runs?.toString() ?? "",
    engines: account?.allowed_engines ?? null,
  }));
  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name.trim(),
        monthly_run_quota: number(form.quota),
        max_concurrent_runs: number(form.concurrent),
        allowed_engines: form.engines,
      };
      return account
        ? call(api.PATCH("/api/admin/integrations/{account_id}", { params: { path: { account_id: account.id } }, body }))
        : call(api.POST("/api/admin/integrations", { body }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      onOpenChange(false);
    },
  });
  const all = form.engines === null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{account ? t("integrations.edit") : t("integrations.new")}</DialogTitle>
          <DialogDescription>{t("integrations.lead")}</DialogDescription>
        </DialogHeader>
        <form
          id="account"
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (form.name.trim()) save.mutate();
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="acc-name">{t("integrations.name")}</Label>
            <Input id="acc-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="DeepWitya" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="acc-quota">{t("integrations.quota")}</Label>
              <Input id="acc-quota" inputMode="numeric" value={form.quota} onChange={(e) => setForm({ ...form, quota: e.target.value })} placeholder={t("integrations.default")} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="acc-concurrent">{t("integrations.concurrent")}</Label>
              <Input id="acc-concurrent" inputMode="numeric" value={form.concurrent} onChange={(e) => setForm({ ...form, concurrent: e.target.value })} placeholder={t("integrations.default")} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>{t("integrations.modes")}</Label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox checked={all} onCheckedChange={(on) => setForm({ ...form, engines: on ? null : engines.map((e) => e.id) })} />
              {t("integrations.allModes")}
            </label>
            {!all && (
              <div className="flex flex-wrap gap-3 pl-6">
                {engines.map((e) => (
                  <label key={e.id} className="flex cursor-pointer items-center gap-2 text-sm">
                    <Checkbox
                      checked={form.engines!.includes(e.id)}
                      onCheckedChange={(on) =>
                        setForm({ ...form, engines: on ? [...form.engines!, e.id] : form.engines!.filter((x) => x !== e.id) })
                      }
                    />
                    {e.label}
                  </label>
                ))}
              </div>
            )}
          </div>
          <ErrorText error={save.error} />
        </form>
        <DialogFooter>
          <Button type="submit" form="account" disabled={!form.name.trim() || save.isPending}>
            {t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type RecentRun = { id: string; topic: string; status: string; title: string | null; queued_at: string };

function AccountCard({ account, revoke }: { account: Account; revoke: (id: string, name: string) => void }) {
  const { t, lang } = useT();
  const recent = (account.recent ?? []) as unknown as RecentRun[];
  const queryClient = useQueryClient();
  const engines = useRunOptions().data?.engines ?? [];
  const [editing, setEditing] = useState(false);
  const [making, setMaking] = useState(false);
  const active = useMutation({
    mutationFn: (is_active: boolean) =>
      call(api.PATCH("/api/admin/integrations/{account_id}", { params: { path: { account_id: account.id } }, body: { is_active } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });
  const label = (id: string) => engines.find((e) => e.id === id)?.label ?? id;
  return (
    <div className="grid gap-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <div className="flex items-center gap-2 font-medium">
            <Plug className="size-4 text-brand" />
            {account.name}
            {!account.is_active && <Badge variant="outline">{t("integrations.off")}</Badge>}
          </div>
          <div className="text-xs text-muted-foreground">
            {t("integrations.usage", { used: account.quota_used, limit: account.quota_limit, runs: account.runs, cost: account.cost_usd.toFixed(2) })}
          </div>
          <div className="flex flex-wrap gap-1">
            {(account.allowed_engines ?? ["*"]).map((e) => (
              <Badge key={e} variant="secondary">
                {e === "*" ? t("integrations.allModes") : label(e)}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={account.is_active} onCheckedChange={(v) => active.mutate(v)} aria-label={t("integrations.active")} />
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil />
            {t("edit")}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setMaking(true)}>
            <Plus />
            {t("tokens.new")}
          </Button>
        </div>
      </div>
      <TokenTable rows={account.tokens} onRevoke={(r) => revoke(r.id, r.name)} />
      <div className="grid gap-1.5">
        <div className="text-xs font-medium text-muted-foreground">{t("integrations.recent")}</div>
        {recent.length ? (
          <ul className="grid gap-1">
            {recent.map((r) => (
              <li key={r.id} className="flex items-center gap-2 text-sm">
                <StatusBadge status={r.status} />
                <Link to="/runs/$runId" params={{ runId: r.id }} className="min-w-0 truncate hover:underline">
                  {r.title || r.topic}
                </Link>
                <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(r.queued_at, lang)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">{t("integrations.noRuns")}</p>
        )}
      </div>
      {editing && <AccountDialog account={account} open={editing} onOpenChange={setEditing} />}
      <NewTokenDialog
        open={making}
        onOpenChange={(o) => {
          setMaking(o);
          if (!o) queryClient.invalidateQueries({ queryKey: ["integrations"] });
        }}
        allowForever
        after={(made) => <McpSetup endpoints={account.endpoints ?? []} token={made.token} compact />}
        make={(body) =>
          call(api.POST("/api/admin/integrations/{account_id}/tokens", { params: { path: { account_id: account.id } }, body }))
        }
      />
    </div>
  );
}

export function McpSettings() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const { confirm, dialog } = useConfirm();
  const [adding, setAdding] = useState(false);
  const settings = useQuery({ queryKey: ["mcp-settings"], queryFn: () => call(api.GET("/api/admin/mcp")) });
  const accounts = useQuery({ queryKey: ["integrations"], queryFn: () => call(api.GET("/api/admin/integrations")) });
  const all = useQuery({ queryKey: ["all-tokens"], queryFn: () => call(api.GET("/api/admin/tokens")) });
  const put = useMutation({
    mutationFn: (body: Schemas["Settings"]) => call(api.PUT("/api/admin/mcp", { body })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mcp-settings"] });
      toast.success(t("common.saved"));
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => call(api.DELETE("/api/admin/tokens/{token_id}", { params: { path: { token_id: id } } })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["all-tokens"] });
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      toast.success(t("tokens.revoked"));
    },
  });
  const ask = (id: string, name: string) => confirm(t("tokens.revokeConfirm", { name }), () => revoke.mutate(id));
  const s = settings.data;
  return (
    <div className="grid gap-8">
      <PortalTo id="settings-actions">
        <Button onClick={() => setAdding(true)}>
          <Plus />
          {t("integrations.new")}
        </Button>
      </PortalTo>
      {s && (
        <div className="divide-y rounded-xl border">
          <Toggle label={t("mcp.enabled")} hint={t("mcp.enabledHint")} checked={s.enabled} onChange={(v) => put.mutate({ ...s, enabled: v })} />
          <Toggle
            label={t("mcp.usersCreate")}
            hint={t("mcp.usersCreateHint")}
            checked={s.users_create_tokens}
            onChange={(v) => put.mutate({ ...s, users_create_tokens: v })}
          />
        </div>
      )}
      <section className="grid gap-3">
        <h2 className="text-sm font-medium">{t("integrations.title")}</h2>
        <p className="text-xs text-muted-foreground">{t("integrations.lead")}</p>
        {accounts.isLoading ? (
          <LoadingRows />
        ) : accounts.data?.length ? (
          accounts.data.map((a) => <AccountCard key={a.id} account={a} revoke={ask} />)
        ) : (
          <p className="rounded-xl border border-dashed py-6 text-center text-sm text-muted-foreground">{t("integrations.none")}</p>
        )}
      </section>
      <section className="grid gap-3">
        <h2 className="text-sm font-medium">{t("mcp.allTokens")}</h2>
        {all.isLoading ? <LoadingRows /> : <TokenTable rows={all.data ?? []} onRevoke={(r) => ask(r.id, r.name)} showOwner />}
      </section>
      <ErrorText error={settings.error ?? accounts.error ?? all.error ?? put.error ?? revoke.error} />
      {adding && <AccountDialog account={null} open={adding} onOpenChange={setAdding} />}
      {dialog}
    </div>
  );
}

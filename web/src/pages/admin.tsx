// Settings: one page per section, tables with every form in a dialog.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import {
  Bot,
  ChartColumn,
  Check,
  CheckCircle2,
  Copy,
  Gauge,
  KeyRound,
  Link2,
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Search as SearchIcon,
  SlidersHorizontal,
  UserPlus,
  UsersRound,
  XCircle,
  Zap,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import { ErrorText, LoadingRows, PageHeader, StatusBadge, Toolbar, errorMessage, formatDate } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useT } from "@/i18n";

const LLM_PROVIDERS = ["openrouter", "gemini", "openai", "groq", "openai-compatible"];
const SEARCH_KINDS = ["searxng", "tavily", "arxiv"];

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function useToastError() {
  const { t } = useT();
  return (e: unknown) => toast.error(errorMessage(e, t));
}

// --- test buttons -------------------------------------------------------------

function TestButton({ kind, id }: { kind: "model" | "search"; id: string }) {
  const { t } = useT();
  const test = useMutation({
    mutationFn: () =>
      kind === "model"
        ? call(api.POST("/api/admin/llm-models/{model_id}/test", { params: { path: { model_id: id } } }))
        : call(api.POST("/api/admin/search-providers/{provider_id}/test", { params: { path: { provider_id: id } } })),
    onSuccess: (r) =>
      r.ok ? toast.success(`${r.message} · ${r.seconds}s`) : toast.error(r.message, { description: `${r.seconds}s` }),
  });
  const r = test.data;
  return (
    <Button variant="outline" size="sm" disabled={test.isPending} onClick={() => test.mutate()}>
      {test.isPending ? (
        <Loader2 className="animate-spin" />
      ) : r ? (
        r.ok ? (
          <CheckCircle2 className="text-success" />
        ) : (
          <XCircle className="text-destructive" />
        )
      ) : (
        <Zap />
      )}
      {test.isPending ? t("admin.testing") : t("admin.test")}
    </Button>
  );
}

// --- users ------------------------------------------------------------------

type User = Schemas["UserOut"];

function LinkBox({ link, email }: { link: string; email: string }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div className="grid gap-3 rounded-lg border bg-muted/50 p-4">
      <p className="text-sm text-muted-foreground">{t("admin.linkLead", { email })}</p>
      <div className="flex gap-2">
        <Input readOnly value={link} onFocus={(e) => e.target.select()} className="bg-background font-mono text-xs" />
        <Button
          type="button"
          variant="outline"
          onClick={async () => {
            await navigator.clipboard.writeText(link);
            setCopied(true);
            toast.success(t("copied"));
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? t("copied") : t("copy")}
        </Button>
      </div>
    </div>
  );
}

function NewUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ email: "", name: "", role: "user" });
  const create = useMutation({
    mutationFn: () => call(api.POST("/api/admin/users", { body: form })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success(t("admin.userCreated"));
    },
  });
  const close = (o: boolean) => {
    if (!o) {
      create.reset();
      setForm({ email: "", name: "", role: "user" });
    }
    onOpenChange(o);
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.newUser")}</DialogTitle>
        </DialogHeader>
        {create.data ? (
          <>
            <LinkBox link={create.data.link} email={create.data.user.email} />
            <DialogFooter>
              <Button onClick={() => close(false)}>{t("common.done")}</Button>
            </DialogFooter>
          </>
        ) : (
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <Field id="u-email" label={t("email")}>
              <Input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </Field>
            <Field id="u-name" label={t("name")}>
              <Input id="u-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field id="u-role" label={t("admin.role")}>
              <Select value={form.role} onValueChange={(role) => setForm({ ...form, role })}>
                <SelectTrigger id="u-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">{t("admin.role.user")}</SelectItem>
                  <SelectItem value="admin">{t("admin.role.admin")}</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            {create.error && <ErrorText error={create.error} />}
            <DialogFooter>
              <Button type="submit" disabled={create.isPending}>
                {t("create")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

const OVERRIDES = [
  ["monthly_run_quota", "admin.override.quota"],
  ["max_concurrent_runs", "admin.override.concurrent"],
  ["max_queued_runs", "admin.override.queued"],
] as const;

function LimitsDialog({ user, onOpenChange }: { user: User | null; onOpenChange: (o: boolean) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>({});
  const current = (k: (typeof OVERRIDES)[number][0]) => values[k] ?? (user?.[k] == null ? "" : String(user[k]));
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/admin/users/{user_id}", {
          params: { path: { user_id: user!.id } },
          body: Object.fromEntries(OVERRIDES.map(([k]) => [k, current(k) === "" ? null : Number(current(k))])),
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success(t("common.saved"));
      setValues({});
      onOpenChange(false);
    },
  });
  return (
    <Dialog open={!!user} onOpenChange={(o) => { setValues({}); onOpenChange(o); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{user?.name}</DialogTitle>
          <DialogDescription>{t("admin.overrides")}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-3 gap-3">
          {OVERRIDES.map(([key, label]) => (
            <Field key={key} id={`o-${key}`} label={t(label)}>
              <Input
                id={`o-${key}`}
                type="number"
                min={0}
                placeholder="—"
                value={current(key)}
                onChange={(e) => setValues({ ...values, [key]: e.target.value })}
              />
            </Field>
          ))}
        </div>
        {save.error && <ErrorText error={save.error} />}
        <DialogFooter>
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Users() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const onError = useToastError();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => call(api.GET("/api/admin/users")) });
  const [creating, setCreating] = useState(false);
  const [limitsFor, setLimitsFor] = useState<User | null>(null);
  const [issued, setIssued] = useState<{ link: string; email: string } | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  const link = useMutation({
    mutationFn: (id: string) => call(api.POST("/api/admin/users/{user_id}/link", { params: { path: { user_id: id } } })),
    onSuccess: (r) => {
      setIssued({ link: r.link, email: r.user.email });
      refresh();
    },
    onError,
  });
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["UserPatch"] }) =>
      call(api.PATCH("/api/admin/users/{user_id}", { params: { path: { user_id: id } }, body })),
    onSuccess: refresh,
    onError,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("admin.users")}</CardTitle>
        <CardAction>
          <Button onClick={() => setCreating(true)}>
            <UserPlus />
            {t("admin.newUser")}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {users.isLoading && <LoadingRows />}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("name")}</TableHead>
              <TableHead>{t("admin.role")}</TableHead>
              <TableHead>{t("admin.thisMonth")}</TableHead>
              <TableHead>{t("admin.hasPassword")}</TableHead>
              <TableHead>{t("admin.active")}</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.data?.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="font-medium">{u.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {u.email} · {formatDate(u.created_at, lang)}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={u.role === "admin" ? "default" : "secondary"}>
                    {u.role === "admin" ? t("admin.role.admin") : t("admin.role.user")}
                  </Badge>
                </TableCell>
                <TableCell className="tabular-nums">
                  {u.quota_used ?? 0} / {u.quota_limit ?? "–"}
                  {!!u.quota_reserved && (
                    <span className="text-xs text-muted-foreground"> · {t("quota.reserved", { reserved: u.quota_reserved })}</span>
                  )}
                </TableCell>
                <TableCell>
                  {u.has_password ? (
                    <CheckCircle2 className="size-4 text-success" />
                  ) : (
                    <span className="text-xs text-muted-foreground">{t("no")}</span>
                  )}
                </TableCell>
                <TableCell>
                  <Switch checked={u.is_active} onCheckedChange={(v) => patch.mutate({ id: u.id, body: { is_active: v } })} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={t("admin.actions")}>
                        <MoreHorizontal />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => (!u.has_password || confirm(t("admin.resetConfirm"))) && link.mutate(u.id)}>
                        <Link2 />
                        {t("admin.newLink")}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setLimitsFor(u)}>
                        <SlidersHorizontal />
                        {t("admin.overrides").split("—")[0].trim()}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <NewUserDialog open={creating} onOpenChange={setCreating} />
      <LimitsDialog user={limitsFor} onOpenChange={(o) => !o && setLimitsFor(null)} />
      <Dialog open={!!issued} onOpenChange={(o) => !o && setIssued(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("admin.link")}</DialogTitle>
          </DialogHeader>
          {issued && <LinkBox {...issued} />}
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// --- models -------------------------------------------------------------------

function KeyDialog({ provider, onOpenChange }: { provider: Schemas["CredentialOut"] | null; onOpenChange: (o: boolean) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [base, setBase] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/admin/llm-credentials/{provider}", {
          params: { path: { provider: provider!.provider } },
          body: { api_key: apiKey, api_base: (base ?? provider?.api_base ?? "") || null },
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-keys"] });
      toast.success(t("common.saved"));
      setApiKey("");
      setBase(null);
      onOpenChange(false);
    },
  });
  return (
    <Dialog open={!!provider} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("admin.editKey", { provider: provider?.provider ?? "" })}</DialogTitle>
            {provider?.key_hint && <DialogDescription>{t("admin.keyHint", { hint: provider.key_hint })}</DialogDescription>}
          </DialogHeader>
          <Field id="k-key" label={t("admin.apiKey")}>
            <Input id="k-key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
          </Field>
          <Field id="k-base" label={`${t("admin.apiBase")} (${t("common.optional")})`}>
            <Input id="k-base" value={base ?? provider?.api_base ?? ""} onChange={(e) => setBase(e.target.value)} />
          </Field>
          {save.error && <ErrorText error={save.error} />}
          <DialogFooter>
            <Button type="submit" disabled={save.isPending}>
              {t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

type ModelForm = {
  id?: string;
  label: string;
  provider: string;
  model: string;
  reasoning: string;
  enabled: boolean;
  is_default: boolean;
  talk: string;
  write: string;
  priceIn: string;
  priceOut: string;
};

const emptyModel: ModelForm = {
  label: "", provider: "openrouter", model: "", reasoning: "", enabled: true, is_default: false,
  talk: "", write: "", priceIn: "", priceOut: "",
};

function toForm(m: Schemas["ModelOut"]): ModelForm {
  const tokens = m.max_tokens as { conversation?: number; writing?: number };
  return {
    id: m.id, label: m.label, provider: m.provider, model: m.model, reasoning: m.reasoning ?? "",
    enabled: m.enabled ?? true, is_default: m.is_default ?? false,
    talk: String(tokens.conversation ?? ""), write: String(tokens.writing ?? ""),
    priceIn: m.price_in_per_mtok == null ? "" : String(m.price_in_per_mtok),
    priceOut: m.price_out_per_mtok == null ? "" : String(m.price_out_per_mtok),
  };
}

function ModelDialog({ form, setForm }: { form: ModelForm | null; setForm: (f: ModelForm | null) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: () => {
      const { id, talk, write, priceIn, priceOut, ...rest } = form!;
      const max_tokens: Record<string, number> = {};
      if (talk) max_tokens.conversation = Number(talk);
      if (write) max_tokens.writing = Number(write);
      const body = {
        ...rest,
        max_tokens,
        price_in_per_mtok: priceIn === "" ? null : priceIn,
        price_out_per_mtok: priceOut === "" ? null : priceOut,
      };
      return id
        ? call(api.PUT("/api/admin/llm-models/{model_id}", { params: { path: { model_id: id } }, body }))
        : call(api.POST("/api/admin/llm-models", { body }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
      toast.success(t("common.saved"));
      setForm(null);
    },
  });
  if (!form) return null;
  const f = form;
  return (
    <Dialog open onOpenChange={(o) => !o && setForm(null)}>
      <DialogContent className="sm:max-w-lg">
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>{f.id ? t("admin.editModel") : t("admin.addModel")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="m-label" label={t("admin.label")}>
              <Input id="m-label" value={f.label} onChange={(e) => setForm({ ...f, label: e.target.value })} required />
            </Field>
            <Field id="m-provider" label={t("admin.provider")}>
              <Select value={f.provider} onValueChange={(provider) => setForm({ ...f, provider })}>
                <SelectTrigger id="m-provider" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LLM_PROVIDERS.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
          <Field id="m-model" label={t("admin.modelId")}>
            <Input
              id="m-model"
              placeholder="google/gemini-3.5-flash-lite"
              className="font-mono text-sm"
              value={f.model}
              onChange={(e) => setForm({ ...f, model: e.target.value })}
              required
            />
          </Field>
          <Field id="m-reasoning" label={t("admin.reasoning")} hint={t("admin.reasoningHelp")}>
            <Input id="m-reasoning" value={f.reasoning} onChange={(e) => setForm({ ...f, reasoning: e.target.value })} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="m-talk" label={t("admin.maxTokens")}>
              <div className="flex gap-2">
                <Input id="m-talk" type="number" min={100} placeholder="500" value={f.talk} onChange={(e) => setForm({ ...f, talk: e.target.value })} />
                <Input type="number" min={100} placeholder="3000" value={f.write} onChange={(e) => setForm({ ...f, write: e.target.value })} />
              </div>
            </Field>
            <Field id="m-price" label={t("admin.price")} hint={t("admin.priceHelp")}>
              <div className="flex gap-2">
                <Input id="m-price" type="number" min={0} step="any" value={f.priceIn} onChange={(e) => setForm({ ...f, priceIn: e.target.value })} />
                <Input type="number" min={0} step="any" value={f.priceOut} onChange={(e) => setForm({ ...f, priceOut: e.target.value })} />
              </div>
            </Field>
          </div>
          <div className="flex gap-6">
            <Label className="flex items-center gap-2 font-normal">
              <Switch checked={f.enabled} onCheckedChange={(enabled) => setForm({ ...f, enabled })} />
              {t("admin.enabled")}
            </Label>
            <Label className="flex items-center gap-2 font-normal">
              <Switch checked={f.is_default} onCheckedChange={(is_default) => setForm({ ...f, is_default })} />
              {t("admin.default")}
            </Label>
          </div>
          {save.error && <ErrorText error={save.error} />}
          <DialogFooter>
            <Button type="submit" disabled={save.isPending}>
              {t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Models() {
  const { t } = useT();
  const keys = useQuery({ queryKey: ["admin-keys"], queryFn: () => call(api.GET("/api/admin/llm-credentials")) });
  const models = useQuery({ queryKey: ["admin-models"], queryFn: () => call(api.GET("/api/admin/llm-models")) });
  const [keyFor, setKeyFor] = useState<Schemas["CredentialOut"] | null>(null);
  const [form, setForm] = useState<ModelForm | null>(null);
  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.models")}</CardTitle>
          <CardAction>
            <Button onClick={() => setForm({ ...emptyModel })}>
              <Plus />
              {t("admin.addModel")}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {models.isLoading && <LoadingRows />}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("admin.label")}</TableHead>
                <TableHead>{t("admin.provider")}</TableHead>
                <TableHead>{t("admin.reasoning")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead className="text-right">{t("admin.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.data?.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    <div className="flex items-center gap-2 font-medium">
                      {m.label}
                      {m.is_default && <Badge variant="secondary">{t("admin.default")}</Badge>}
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">{m.model}</div>
                  </TableCell>
                  <TableCell>{m.provider}</TableCell>
                  <TableCell className="font-mono text-xs">{m.reasoning || "—"}</TableCell>
                  <TableCell>
                    <Badge variant={m.enabled ? "outline" : "secondary"}>{m.enabled ? t("admin.enabled") : t("no")}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <TestButton kind="model" id={m.id} />
                      <Button variant="ghost" size="icon" aria-label={t("edit")} onClick={() => setForm(toForm(m))}>
                        <Pencil />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("admin.keys")}</CardTitle>
          <CardDescription>{t("admin.keysLead")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableBody>
              {keys.data?.map((k) => (
                <TableRow key={k.provider}>
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-2">
                      <KeyRound className="size-4 text-muted-foreground" />
                      {k.provider}
                    </span>
                  </TableCell>
                  <TableCell>
                    {k.key_hint ? (
                      <Badge variant="outline" className="font-mono">
                        {k.key_hint}
                      </Badge>
                    ) : (
                      <span className="text-sm text-muted-foreground">{t("admin.noKey")}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" onClick={() => setKeyFor(k)}>
                      {t("edit")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <KeyDialog provider={keyFor} onOpenChange={(o) => !o && setKeyFor(null)} />
      <ModelDialog form={form} setForm={setForm} />
    </div>
  );
}

// --- Search Providers -----------------------------------------------------------

type SearchForm = Schemas["SearchIn"] & { id?: string };

function SearchDialog({ form, setForm }: { form: SearchForm | null; setForm: (f: SearchForm | null) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: () => {
      const { id, ...body } = form!;
      return id
        ? call(api.PUT("/api/admin/search-providers/{provider_id}", { params: { path: { provider_id: id } }, body }))
        : call(api.POST("/api/admin/search-providers", { body }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-search"] });
      toast.success(t("common.saved"));
      setForm(null);
    },
  });
  if (!form) return null;
  const f = form;
  return (
    <Dialog open onOpenChange={(o) => !o && setForm(null)}>
      <DialogContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>{f.id ? t("admin.editSearch") : t("admin.addSearch")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="s-label" label={t("admin.label")}>
              <Input id="s-label" value={f.label} onChange={(e) => setForm({ ...f, label: e.target.value })} required />
            </Field>
            <Field id="s-kind" label={t("admin.kind")}>
              <Select value={f.kind} onValueChange={(kind) => setForm({ ...f, kind })}>
                <SelectTrigger id="s-kind" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEARCH_KINDS.map((k) => (
                    <SelectItem key={k} value={k}>
                      {k}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
          {f.kind === "searxng" && (
            <>
              <Field id="s-endpoint" label={t("admin.endpoint")}>
                <Input id="s-endpoint" value={f.endpoint ?? ""} onChange={(e) => setForm({ ...f, endpoint: e.target.value })} required />
              </Field>
              <Field id="s-engines" label={`${t("admin.engines")} (${t("common.optional")})`}>
                <Input id="s-engines" value={f.engines ?? ""} onChange={(e) => setForm({ ...f, engines: e.target.value })} />
              </Field>
            </>
          )}
          {f.kind === "tavily" && (
            <Field id="s-key" label={t("admin.apiKey")}>
              <Input id="s-key" type="password" autoComplete="off" value={f.api_key ?? ""} onChange={(e) => setForm({ ...f, api_key: e.target.value })} />
            </Field>
          )}
          <div className="flex gap-6">
            <Label className="flex items-center gap-2 font-normal">
              <Switch checked={f.enabled ?? true} onCheckedChange={(enabled) => setForm({ ...f, enabled })} />
              {t("admin.enabled")}
            </Label>
            <Label className="flex items-center gap-2 font-normal">
              <Switch checked={f.is_default ?? false} onCheckedChange={(is_default) => setForm({ ...f, is_default })} />
              {t("admin.default")}
            </Label>
          </div>
          {save.error && <ErrorText error={save.error} />}
          <DialogFooter>
            <Button type="submit" disabled={save.isPending}>
              {t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Search() {
  const { t } = useT();
  const providers = useQuery({ queryKey: ["admin-search"], queryFn: () => call(api.GET("/api/admin/search-providers")) });
  const [form, setForm] = useState<SearchForm | null>(null);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("admin.search")}</CardTitle>
        <CardAction>
          <Button onClick={() => setForm({ label: "", kind: "searxng", enabled: true, is_default: false })}>
            <Plus />
            {t("admin.addSearch")}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("admin.label")}</TableHead>
              <TableHead>{t("admin.kind")}</TableHead>
              <TableHead>{t("common.status")}</TableHead>
              <TableHead className="text-right">{t("admin.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {providers.data?.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="flex items-center gap-2 font-medium">
                    {p.label}
                    {p.is_default && <Badge variant="secondary">{t("admin.default")}</Badge>}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {p.endpoint}
                    {p.key_hint && ` · ${t("admin.keyHint", { hint: p.key_hint })}`}
                  </div>
                </TableCell>
                <TableCell>{p.kind}</TableCell>
                <TableCell>
                  <Badge variant={p.enabled ? "outline" : "secondary"}>{p.enabled ? t("admin.enabled") : t("no")}</Badge>
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    <TestButton kind="search" id={p.id} />
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("edit")}
                      onClick={() =>
                        setForm({ id: p.id, label: p.label, kind: p.kind, endpoint: p.endpoint, engines: p.engines, enabled: p.enabled, is_default: p.is_default })
                      }
                    >
                      <Pencil />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <SearchDialog form={form} setForm={setForm} />
    </Card>
  );
}

// --- limits -----------------------------------------------------------------------

function Limits() {
  const { t } = useT();
  const limits = useQuery({ queryKey: ["admin-limits"], queryFn: () => call(api.GET("/api/admin/limits")) });
  const [form, setForm] = useState<Schemas["Limits"] | null>(null);
  const current = form ?? limits.data;
  const save = useMutation({
    mutationFn: () => call(api.PUT("/api/admin/limits", { body: current! })),
    onSuccess: () => toast.success(t("common.saved")),
  });
  if (!current) return <LoadingRows />;
  const num = (key: keyof Schemas["Limits"], label: string) => (
    <Field id={`l-${key}`} label={label}>
      <Input
        id={`l-${key}`}
        type="number"
        min={0}
        value={String(current[key] ?? "")}
        onChange={(e) => setForm({ ...current, [key]: Number(e.target.value) })}
      />
    </Field>
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("admin.limits")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          {num("max_concurrent_total", t("admin.limit.total"))}
          {num("max_concurrent_per_user", t("admin.limit.perUser"))}
          {num("max_queued_per_user", t("admin.limit.queued"))}
          {num("monthly_run_quota", t("admin.limit.quota"))}
          {num("run_deadline_minutes", t("admin.limit.deadline"))}
          <div className="flex items-end sm:col-span-2">
            <Button type="submit" disabled={save.isPending}>
              {t("save")}
            </Button>
          </div>
          {save.error && (
            <div className="sm:col-span-2">
              <ErrorText error={save.error} />
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

// --- usage ----------------------------------------------------------------------------

function lastMonths(n: number) {
  const out: string[] = [];
  const d = new Date();
  for (let i = 0; i < n; i++) {
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

function usd(v: string | number | null | undefined) {
  if (v == null) return "–";
  return `$${Number(v).toFixed(Number(v) < 1 ? 4 : 2)}`;
}

function Usage() {
  const { t, lang } = useT();
  const months = lastMonths(6);
  const [month, setMonth] = useState(months[0]);
  const usage = useQuery({
    queryKey: ["admin-usage", month],
    queryFn: () => call(api.GET("/api/admin/usage", { params: { query: { month } } })),
  });
  const runs = useQuery({
    queryKey: ["admin-runs"],
    queryFn: () => call(api.GET("/api/admin/runs", { params: { query: { limit: 50 } } })),
  });
  const n = (v: number) => v.toLocaleString(lang === "th" ? "th-TH" : "en-GB");
  const right = "text-right tabular-nums";
  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.usage")}</CardTitle>
          <CardDescription>{t("usage.privacy")}</CardDescription>
          <CardAction>
            <Select value={month} onValueChange={setMonth}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {months.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardAction>
        </CardHeader>
        <CardContent>
          {usage.data?.rows.length === 0 && <p className="text-sm text-muted-foreground">{t("usage.none")}</p>}
          {!!usage.data?.rows.length && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("usage.user")}</TableHead>
                  <TableHead className={right}>{t("usage.runs")}</TableHead>
                  <TableHead className={right}>{t("usage.ok")}</TableHead>
                  <TableHead className={right}>{t("usage.failed")}</TableHead>
                  <TableHead className={right}>{t("usage.refunded")}</TableHead>
                  <TableHead className={right}>{t("usage.tokens")}</TableHead>
                  <TableHead className={right}>{t("usage.searches")}</TableHead>
                  <TableHead className={right}>{t("usage.cost")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usage.data.rows.map((r) => (
                  <TableRow key={r.user_id}>
                    <TableCell>{r.email}</TableCell>
                    <TableCell className={right}>{r.runs}</TableCell>
                    <TableCell className={right}>{r.succeeded}</TableCell>
                    <TableCell className={right}>{r.failed}</TableCell>
                    <TableCell className={right}>{r.refunded}</TableCell>
                    <TableCell className={right}>
                      {n(r.tokens_in)} / {n(r.tokens_out)}
                    </TableCell>
                    <TableCell className={right}>{r.search_calls}</TableCell>
                    <TableCell className={right}>
                      {usd(r.cost_usd)}
                      {r.cost_incomplete && <div className="text-xs text-warning">{t("usage.unknown")}</div>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell>{t("usage.total")}</TableCell>
                  <TableCell colSpan={6} />
                  <TableCell className={right}>
                    {usd(usage.data.total_cost_usd)}
                    {usage.data.rows.some((r) => r.cost_incomplete) && (
                      <div className="text-xs font-normal text-warning">{t("usage.unknown")}</div>
                    )}
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("usage.recent")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("common.created")}</TableHead>
                <TableHead>{t("usage.user")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead>{t("run.model")}</TableHead>
                <TableHead className={right}>{t("usage.tokens")}</TableHead>
                <TableHead className={right}>{t("usage.cost")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.data?.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{formatDate(r.queued_at, lang)}</TableCell>
                  <TableCell>{r.email}</TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                    {r.reason && r.reason !== r.status && r.reason !== "cancelled" && (
                      <div className="mt-1 text-xs text-muted-foreground">{r.reason}</div>
                    )}
                  </TableCell>
                  <TableCell className="text-xs">{r.model_label}</TableCell>
                  <TableCell className={right}>{r.tokens_in != null ? `${n(r.tokens_in)} / ${n(r.tokens_out ?? 0)}` : "–"}</TableCell>
                  <TableCell className={right}>{usd(r.cost_usd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

// The settings sections, each its own address; the sidebar lists them under
// ตั้งค่าระบบ.
export const SETTINGS = [
  { id: "users", label: "admin.users", lead: "settings.usersLead", icon: UsersRound, page: Users },
  { id: "models", label: "admin.models", lead: "settings.modelsLead", icon: Bot, page: Models },
  { id: "search", label: "admin.search", lead: "settings.searchLead", icon: SearchIcon, page: Search },
  { id: "limits", label: "admin.limits", lead: "settings.limitsLead", icon: Gauge, page: Limits },
  { id: "usage", label: "admin.usage", lead: "settings.usageLead", icon: ChartColumn, page: Usage },
] as const;

export function AdminPage() {
  const { t } = useT();
  const { section } = useParams({ from: "/app/settings/$section" });
  const current = SETTINGS.find((s) => s.id === section) ?? SETTINGS[0];
  const Page = current.page;
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-8">
      <Toolbar>
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/settings/$section" params={{ section: "users" }}>
                  {t("nav.admin")}
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{t(current.label)}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </Toolbar>
      <PageHeader title={t(current.label)} description={t(current.lead)} />
      <Page />
    </div>
  );
}

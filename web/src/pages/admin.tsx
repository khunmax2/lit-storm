// Settings: one page per section, tables with every form in a dialog.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import {
  Bot,
  ChartColumn,
  Check,
  ChevronDown,
  CheckCircle2,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  FlaskConical,
  Gauge,
  Globe,
  GraduationCap,
  Info,
  KeyRound,
  Link2,
  Loader2,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Search as SearchIcon,
  Server,
  SlidersHorizontal,
  UserPlus,
  UsersRound,
  XCircle,
  Zap,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import { ErrorText, LoadingRows, PageHeader, PortalTo, StatusBadge, Toolbar, errorMessage, formatDate } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

const LLM_PROVIDERS = ["openrouter", "gemini", "openai", "groq", "openai-compatible"];
const SEARCH_KINDS = ["searxng", "tavily", "arxiv"];

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid content-start gap-2">
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
      <SectionActions>
        <Button onClick={() => setCreating(true)}>
          <UserPlus />
          {t("admin.newUser")}
        </Button>
      </SectionActions>
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

// The "try it before saving" box both setting dialogs share.
type DraftResult = Schemas["CheckOut"] & { for: string };

function DraftTest({
  lead,
  onTest,
  pending,
  error,
  result,
  stale,
  okText,
  failText,
  query,
}: {
  lead: string;
  onTest: () => void;
  pending: boolean;
  error: unknown;
  result: DraftResult | undefined;
  stale: boolean;
  okText: (r: DraftResult) => string;
  failText: string;
  /** A search's test query; models have none. */
  query?: { value: string; set: (v: string) => void; placeholder: string };
}) {
  const { t } = useT();
  const button = (
    <Button type="button" variant="outline" className="shrink-0 bg-background" disabled={pending} onClick={onTest}>
      {pending ? <Loader2 className="animate-spin" /> : <Zap />}
      {pending ? t("admin.testing") : t("admin.test")}
    </Button>
  );
  return (
    <div className="grid gap-3 rounded-xl border bg-muted/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <FlaskConical className="size-4" />
            {t("searchKind.testTitle")}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{lead}</p>
        </div>
        {!query && button}
      </div>
      {query && (
        <div className="flex gap-2">
          <Input
            aria-label={t("searchKind.testQuery")}
            placeholder={query.placeholder}
            value={query.value}
            onChange={(e) => query.set(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onTest();
              }
            }}
            className="bg-background"
          />
          {button}
        </div>
      )}
      <div aria-live="polite" className="empty:hidden">
        {!!error && <ErrorText error={error} />}
        {result && !stale && result.ok && (
          <div className="rounded-lg border border-success/30 bg-success-soft p-3 text-sm">
            <div className="flex items-center gap-2 font-medium text-success">
              <CheckCircle2 className="size-4" />
              {okText(result)}
            </div>
            {!!result.samples?.length && (
              <ul className="mt-2 grid gap-1 pl-6 text-foreground/80">
                {result.samples.map((title, i) => (
                  <li key={i} className="list-disc truncate">
                    {title}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {result && !stale && !result.ok && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium text-destructive">
              <XCircle className="size-4" />
              {failText}
            </div>
            <p className="mt-1 pl-6 font-mono text-xs break-words text-foreground/80">{result.message}</p>
          </div>
        )}
        {stale && <p className="text-xs text-muted-foreground">{t("searchKind.stale")}</p>}
      </div>
    </div>
  );
}

/** A switch row with what it does under its name. */
function SwitchRow({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
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

// What each LLM provider is, shown as cards.
const LLM_INFO: Record<string, { name: string; lead: Key; example: string; keyUrl?: string; modelsUrl?: string }> = {
  openrouter: {
    name: "OpenRouter",
    lead: "modelKind.openrouter",
    example: "google/gemini-3.5-flash-lite",
    keyUrl: "https://openrouter.ai/settings/keys",
    modelsUrl: "https://openrouter.ai/models",
  },
  gemini: {
    name: "Gemini",
    lead: "modelKind.gemini",
    example: "gemini-2.5-flash",
    keyUrl: "https://aistudio.google.com/apikey",
    modelsUrl: "https://ai.google.dev/gemini-api/docs/models",
  },
  openai: {
    name: "OpenAI",
    lead: "modelKind.openai",
    example: "gpt-5-mini",
    keyUrl: "https://platform.openai.com/api-keys",
    modelsUrl: "https://platform.openai.com/docs/models",
  },
  groq: {
    name: "Groq",
    lead: "modelKind.groq",
    example: "llama-3.3-70b-versatile",
    keyUrl: "https://console.groq.com/keys",
    modelsUrl: "https://console.groq.com/docs/models",
  },
  "openai-compatible": { name: "OpenAI-compatible", lead: "modelKind.compatible", example: "my-model" },
};

const REASONING_PRESETS = ["", "off", "effort:minimal", "effort:low", "effort:medium"];

// The fields a model test depends on.
const modelTestedWith = (f: ModelForm, key: string, base: string) =>
  JSON.stringify([f.provider, f.model, f.reasoning, f.talk, key, base]);

function ModelDialog({
  form,
  setForm,
  keys,
}: {
  form: ModelForm | null;
  setForm: (f: ModelForm | null) => void;
  keys: Schemas["CredentialOut"][];
}) {
  const { t } = useT();
  const queryClient = useQueryClient();
  // The provider's key, typed here: saved for the provider with the model.
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [changingKey, setChangingKey] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const stored = keys.find((k) => k.provider === form?.provider);
  const needsBase = form?.provider === "openai-compatible";

  const save = useMutation({
    mutationFn: async () => {
      const { id, talk, write, priceIn, priceOut, ...rest } = form!;
      if (apiKey.trim())
        await call(
          api.PUT("/api/admin/llm-credentials/{provider}", {
            params: { path: { provider: rest.provider } },
            body: { api_key: apiKey.trim(), api_base: (apiBase.trim() || stored?.api_base) ?? null },
          }),
        );
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
      queryClient.invalidateQueries({ queryKey: ["admin-keys"] });
      toast.success(t("common.saved"));
      setForm(null);
    },
  });
  const check = useMutation({
    mutationFn: (f: ModelForm) =>
      call(
        api.POST("/api/admin/llm-models/check", {
          body: {
            provider: f.provider,
            model: f.model,
            reasoning: f.reasoning,
            max_tokens: f.talk ? { conversation: Number(f.talk) } : {},
            api_key: apiKey.trim() || null,
            api_base: apiBase.trim() || null,
          },
        }),
      ).then((r) => ({ ...r, for: modelTestedWith(f, apiKey, apiBase) })),
  });
  useEffect(() => {
    if (!form) {
      check.reset();
      save.reset();
      setApiKey("");
      setApiBase("");
      setChangingKey(false);
      setShowKey(false);
      setAdvanced(false);
    }
  }, [form]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!form) return null;
  const f = form;
  const info = LLM_INFO[f.provider];
  const result = check.data;
  const stale = !!result && result.for !== modelTestedWith(f, apiKey, apiBase);
  const hasKey = !!stored?.key_hint;
  const askKey = !hasKey || changingKey;

  const chooseProvider = (provider: string) => {
    setForm({ ...f, provider });
    setApiKey("");
    setApiBase("");
    setChangingKey(false);
  };

  return (
    <Dialog open onOpenChange={(o) => !o && setForm(null)}>
      <DialogContent className="gap-0 p-0 sm:max-w-2xl">
        <form
          className="flex max-h-[90svh] flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <DialogHeader className="border-b px-6 pt-6 pb-4">
            <DialogTitle className="text-lg">{f.id ? t("admin.editModel") : t("admin.addModel")}</DialogTitle>
            <DialogDescription>{t("modelKind.lead")}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 overflow-y-auto px-6 py-5">
            {/* 1. Who serves it */}
            <fieldset className="grid gap-2">
              <legend className="mb-2 text-sm font-medium">{t("admin.provider")}</legend>
              <div role="radiogroup" aria-label={t("admin.provider")} className="grid gap-2 sm:grid-cols-3">
                {LLM_PROVIDERS.map((p) => {
                  const k = LLM_INFO[p];
                  const active = p === f.provider;
                  const hint = keys.find((c) => c.provider === p)?.key_hint;
                  return (
                    <button
                      key={p}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => chooseProvider(p)}
                      className={cn(
                        "flex flex-col gap-1.5 rounded-xl border p-3 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                        active ? "border-foreground/70 bg-muted/40 ring-1 ring-foreground/70" : "hover:bg-muted/40",
                      )}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-medium">{k.name}</span>
                        <span
                          className={cn(
                            "flex size-4 shrink-0 items-center justify-center rounded-full border",
                            active && "border-foreground bg-foreground text-background",
                          )}
                        >
                          {active && <Check className="size-3" />}
                        </span>
                      </span>
                      <span className="text-xs leading-snug text-muted-foreground">{t(k.lead)}</span>
                      <span className="mt-auto flex items-center gap-1.5 pt-1 text-xs">
                        <span className={cn("size-1.5 rounded-full", hint ? "bg-success" : "bg-warning")} />
                        {hint ? (
                          <span className="font-mono text-muted-foreground">{hint}</span>
                        ) : (
                          <span className="text-muted-foreground">{t("admin.noKey")}</span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {/* 2. Which model, and what people see */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="m-model">{t("admin.modelId")}</Label>
                  {info.modelsUrl && (
                    <a
                      href={info.modelsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                    >
                      {t("modelKind.browse")}
                      <ExternalLink className="size-3" />
                    </a>
                  )}
                </div>
                <Input
                  id="m-model"
                  placeholder={info.example}
                  className="font-mono text-sm"
                  value={f.model}
                  onChange={(e) => setForm({ ...f, model: e.target.value })}
                  required
                />
                <p className="text-xs text-muted-foreground">{t("modelKind.modelHint", { provider: info.name })}</p>
              </div>
              <Field id="m-label" label={t("admin.label")} hint={t("modelKind.labelHint")}>
                <Input
                  id="m-label"
                  placeholder="Gemini 3.5 Flash Lite"
                  value={f.label}
                  onChange={(e) => setForm({ ...f, label: e.target.value })}
                  required
                />
              </Field>
            </div>

            {/* 3. The provider's key */}
            <div className="grid gap-3 rounded-xl border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <KeyRound className="size-4" />
                    {t("modelKind.keyTitle", { provider: info.name })}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{t("modelKind.keyLead", { provider: info.name })}</p>
                </div>
                {info.keyUrl && (
                  <a
                    href={info.keyUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {t("searchKind.getKey")}
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
              {!askKey ? (
                <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 px-3 py-2 text-sm">
                  <span className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-success" />
                    {t("modelKind.keyStored")}
                    <span className="font-mono text-xs text-muted-foreground">{stored?.key_hint}</span>
                  </span>
                  <Button type="button" variant="ghost" size="sm" onClick={() => setChangingKey(true)}>
                    {t("modelKind.changeKey")}
                  </Button>
                </div>
              ) : (
                <div className="relative">
                  <Input
                    aria-label={t("admin.apiKey")}
                    type={showKey ? "text" : "password"}
                    autoComplete="off"
                    spellCheck={false}
                    className="pr-10 font-mono"
                    placeholder={hasKey ? t("searchKind.keepKey", { hint: stored!.key_hint }) : "sk-…"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute top-1/2 right-1 size-7 -translate-y-1/2 text-muted-foreground"
                    aria-label={showKey ? t("searchKind.hideKey") : t("searchKind.showKey")}
                    onClick={() => setShowKey(!showKey)}
                  >
                    {showKey ? <EyeOff /> : <Eye />}
                  </Button>
                </div>
              )}
              {needsBase && (
                <Field id="m-base" label={t("admin.apiBase")} hint={t("modelKind.baseHint")}>
                  <Input
                    id="m-base"
                    placeholder={stored?.api_base || "http://localhost:11434/v1"}
                    value={apiBase}
                    onChange={(e) => setApiBase(e.target.value)}
                  />
                </Field>
              )}
            </div>

            {/* 4. Tuning, folded away */}
            <Collapsible open={advanced} onOpenChange={setAdvanced} className="rounded-xl border">
              <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm font-medium">
                <span>
                  {t("modelKind.advanced")}
                  <span className="block text-xs font-normal text-muted-foreground">{t("modelKind.advancedLead")}</span>
                </span>
                <ChevronDown className={cn("size-4 shrink-0 transition-transform", advanced && "rotate-180")} />
              </CollapsibleTrigger>
              <CollapsibleContent className="grid gap-4 border-t p-4">
                <div className="grid gap-2">
                  <Label htmlFor="m-reasoning">{t("admin.reasoning")}</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {REASONING_PRESETS.map((r) => (
                      <button
                        key={r || "none"}
                        type="button"
                        onClick={() => setForm({ ...f, reasoning: r })}
                        className={cn(
                          "rounded-md border px-2 py-1 font-mono text-xs transition-colors",
                          f.reasoning === r ? "border-foreground bg-foreground text-background" : "hover:bg-muted",
                        )}
                      >
                        {r || t("modelKind.reasoningDefault")}
                      </button>
                    ))}
                  </div>
                  <Input
                    id="m-reasoning"
                    className="font-mono text-sm"
                    placeholder="budget:800"
                    value={f.reasoning}
                    onChange={(e) => setForm({ ...f, reasoning: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">{t("modelKind.reasoningHint")}</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field id="m-talk" label={t("modelKind.talkTokens")} hint={t("modelKind.talkHint")}>
                    <Input id="m-talk" type="number" min={100} placeholder="500" value={f.talk} onChange={(e) => setForm({ ...f, talk: e.target.value })} />
                  </Field>
                  <Field id="m-write" label={t("modelKind.writeTokens")} hint={t("modelKind.writeHint")}>
                    <Input id="m-write" type="number" min={100} placeholder="3000" value={f.write} onChange={(e) => setForm({ ...f, write: e.target.value })} />
                  </Field>
                  <Field id="m-price-in" label={t("modelKind.priceIn")} hint={t("admin.priceHelp")}>
                    <Input id="m-price-in" type="number" min={0} step="any" placeholder="0.10" value={f.priceIn} onChange={(e) => setForm({ ...f, priceIn: e.target.value })} />
                  </Field>
                  <Field id="m-price-out" label={t("modelKind.priceOut")}>
                    <Input id="m-price-out" type="number" min={0} step="any" placeholder="0.40" value={f.priceOut} onChange={(e) => setForm({ ...f, priceOut: e.target.value })} />
                  </Field>
                </div>
              </CollapsibleContent>
            </Collapsible>

            {/* 5. Try it before saving */}
            <DraftTest
              lead={t("modelKind.testLead")}
              onTest={() => check.mutate(f)}
              pending={check.isPending}
              error={check.error}
              result={result}
              stale={stale}
              okText={(r) => t("modelKind.ok", { reply: r.message, s: r.seconds })}
              failText={t("modelKind.failed")}
            />

            {/* 6. Who can use it */}
            <div className="divide-y rounded-xl border">
              <SwitchRow
                label={t("admin.enabled")}
                hint={t("modelKind.enabledHint")}
                checked={f.enabled}
                onChange={(enabled) => setForm({ ...f, enabled })}
              />
              <SwitchRow
                label={t("admin.default")}
                hint={t("modelKind.defaultHint")}
                checked={f.is_default}
                onChange={(is_default) => setForm({ ...f, is_default })}
              />
            </div>
            {save.error && <ErrorText error={save.error} />}
          </div>

          <div className="flex flex-col-reverse gap-2 border-t bg-muted/40 px-6 py-4 sm:flex-row sm:items-center sm:justify-end">
            {result && !stale && !result.ok && (
              <span className="text-xs text-muted-foreground sm:mr-auto">{t("searchKind.saveAnyway")}</span>
            )}
            <Button type="button" variant="outline" onClick={() => setForm(null)}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" />}
              {t("save")}
            </Button>
          </div>
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
        <SectionActions>
            <Button onClick={() => setForm({ ...emptyModel })}>
              <Plus />
              {t("admin.addModel")}
            </Button>
        </SectionActions>
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
      <ModelDialog form={form} setForm={setForm} keys={keys.data ?? []} />
    </div>
  );
}

// --- Search Providers -----------------------------------------------------------

type SearchForm = Schemas["SearchIn"] & { id?: string; key_hint?: string };

// What each kind is, shown as cards to choose from.
const SEARCH_KIND_INFO: Record<string, { name: string; icon: typeof Globe; lead: Key; tag: Key; keyUrl?: string }> = {
  searxng: { name: "SearXNG", icon: Server, lead: "searchKind.searxng", tag: "searchKind.tagSelf" },
  tavily: {
    name: "Tavily",
    icon: Globe,
    lead: "searchKind.tavily",
    tag: "searchKind.tagKey",
    keyUrl: "https://app.tavily.com/home",
  },
  arxiv: { name: "arXiv", icon: GraduationCap, lead: "searchKind.arxiv", tag: "searchKind.tagFree" },
};

// The fields a test depends on; a result is shown only while they match.
const testedWith = (f: SearchForm) => JSON.stringify([f.kind, f.endpoint ?? "", f.engines ?? "", f.api_key ?? ""]);

function SearchDialog({ form, setForm }: { form: SearchForm | null; setForm: (f: SearchForm | null) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [showKey, setShowKey] = useState(false);
  const [query, setQuery] = useState("");
  const save = useMutation({
    mutationFn: () => {
      const { id, key_hint: _hint, ...body } = form!;
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
  const check = useMutation({
    mutationFn: (f: SearchForm) =>
      call(
        api.POST("/api/admin/search-providers/check", {
          body: {
            kind: f.kind,
            endpoint: f.endpoint,
            engines: f.engines,
            // Blank while editing: try the key already stored.
            api_key: f.api_key || (f.id ? null : ""),
            id: f.id ?? null,
            query: query || null,
          },
        }),
      ).then((r) => ({ ...r, for: testedWith(f) })),
  });
  useEffect(() => {
    if (!form) {
      check.reset();
      save.reset();
      setShowKey(false);
      setQuery("");
    }
  }, [form]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!form) return null;
  const f = form;
  const info = SEARCH_KIND_INFO[f.kind];
  const result = check.data;
  const stale = !!result && result.for !== testedWith(f);

  const chooseKind = (kind: string) => {
    // Follow the kind with the name, unless the name was typed by hand.
    const named = !f.label || Object.values(SEARCH_KIND_INFO).some((k) => k.name === f.label);
    setForm({ ...f, kind, label: named ? SEARCH_KIND_INFO[kind].name : f.label });
  };

  return (
    <Dialog open onOpenChange={(o) => !o && setForm(null)}>
      <DialogContent className="gap-0 p-0 sm:max-w-2xl">
        <form
          className="flex max-h-[90svh] flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <DialogHeader className="border-b px-6 pt-6 pb-4">
            <DialogTitle className="text-lg">{f.id ? t("admin.editSearch") : t("admin.addSearch")}</DialogTitle>
            <DialogDescription>{t("searchKind.lead")}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 overflow-y-auto px-6 py-5">
            {/* 1. What kind of service */}
            <fieldset className="grid gap-2">
              <legend className="mb-2 text-sm font-medium">{t("admin.kind")}</legend>
              <div role="radiogroup" aria-label={t("admin.kind")} className="grid gap-2 sm:grid-cols-3">
                {SEARCH_KINDS.map((kind) => {
                  const k = SEARCH_KIND_INFO[kind];
                  const active = kind === f.kind;
                  return (
                    <button
                      key={kind}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => chooseKind(kind)}
                      className={cn(
                        "flex flex-col gap-2 rounded-xl border p-3 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                        active ? "border-foreground/70 bg-muted/40 ring-1 ring-foreground/70" : "hover:bg-muted/40",
                      )}
                    >
                      <span className="flex items-center justify-between">
                        <span className="flex size-8 items-center justify-center rounded-lg bg-muted">
                          <k.icon className="size-4" />
                        </span>
                        <span
                          className={cn(
                            "flex size-4 items-center justify-center rounded-full border",
                            active && "border-foreground bg-foreground text-background",
                          )}
                        >
                          {active && <Check className="size-3" />}
                        </span>
                      </span>
                      <span className="font-medium">{k.name}</span>
                      <span className="text-xs leading-snug text-muted-foreground">{t(k.lead)}</span>
                      <Badge variant="secondary" className="mt-auto w-fit">
                        {t(k.tag)}
                      </Badge>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {/* 2. How to reach it */}
            <div className="grid gap-4">
              <Field id="s-label" label={t("admin.label")} hint={t("searchKind.labelHint")}>
                <Input id="s-label" value={f.label} onChange={(e) => setForm({ ...f, label: e.target.value })} required />
              </Field>
              {f.kind === "searxng" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field id="s-endpoint" label={t("admin.endpoint")} hint={t("searchKind.endpointHint")}>
                    <Input
                      id="s-endpoint"
                      placeholder="http://searxng:8080"
                      value={f.endpoint ?? ""}
                      onChange={(e) => setForm({ ...f, endpoint: e.target.value })}
                      required
                    />
                  </Field>
                  <Field
                    id="s-engines"
                    label={`${t("admin.engines")} (${t("common.optional")})`}
                    hint={t("searchKind.enginesHint")}
                  >
                    <Input
                      id="s-engines"
                      placeholder="arxiv,pubmed,openalex"
                      value={f.engines ?? ""}
                      onChange={(e) => setForm({ ...f, engines: e.target.value })}
                    />
                  </Field>
                </div>
              )}
              {f.kind === "tavily" && (
                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="s-key">{t("admin.apiKey")}</Label>
                    {info.keyUrl && (
                      <a
                        href={info.keyUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      >
                        {t("searchKind.getKey")}
                        <ExternalLink className="size-3" />
                      </a>
                    )}
                  </div>
                  <div className="relative">
                    <Input
                      id="s-key"
                      type={showKey ? "text" : "password"}
                      autoComplete="off"
                      spellCheck={false}
                      className="pr-10 font-mono"
                      placeholder={f.key_hint ? t("searchKind.keepKey", { hint: f.key_hint }) : "tvly-…"}
                      value={f.api_key ?? ""}
                      onChange={(e) => setForm({ ...f, api_key: e.target.value })}
                      required={!f.key_hint}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute top-1/2 right-1 size-7 -translate-y-1/2 text-muted-foreground"
                      aria-label={showKey ? t("searchKind.hideKey") : t("searchKind.showKey")}
                      onClick={() => setShowKey(!showKey)}
                    >
                      {showKey ? <EyeOff /> : <Eye />}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">{t("searchKind.keyHint")}</p>
                </div>
              )}
              {f.kind === "arxiv" && (
                <p className="flex gap-2 rounded-lg bg-muted/60 px-3 py-2.5 text-sm text-muted-foreground">
                  <Info className="mt-0.5 size-4 shrink-0" />
                  {t("searchKind.arxivNote")}
                </p>
              )}
            </div>

            {/* 3. Try it before saving */}
            <DraftTest
              lead={t("searchKind.testLead")}
              onTest={() => check.mutate(f)}
              pending={check.isPending}
              error={check.error}
              result={result}
              stale={stale}
              okText={(r) => t("searchKind.ok", { n: r.samples?.length ?? 0, s: r.seconds })}
              failText={t("searchKind.failed")}
              query={{ value: query, set: setQuery, placeholder: "retrieval augmented generation" }}
            />

            {/* 4. Who can use it */}
            <div className="divide-y rounded-xl border">
              <SwitchRow
                label={t("admin.enabled")}
                hint={t("searchKind.enabledHint")}
                checked={f.enabled ?? true}
                onChange={(enabled) => setForm({ ...f, enabled })}
              />
              <SwitchRow
                label={t("admin.default")}
                hint={t("searchKind.defaultHint")}
                checked={f.is_default ?? false}
                onChange={(is_default) => setForm({ ...f, is_default })}
              />
            </div>
            {save.error && <ErrorText error={save.error} />}
          </div>

          <div className="flex flex-col-reverse gap-2 border-t bg-muted/40 px-6 py-4 sm:flex-row sm:items-center sm:justify-end">
            {result && !stale && !result.ok && (
              <span className="text-xs text-muted-foreground sm:mr-auto">{t("searchKind.saveAnyway")}</span>
            )}
            <Button type="button" variant="outline" onClick={() => setForm(null)}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" />}
              {t("save")}
            </Button>
          </div>
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
      <SectionActions>
          <Button onClick={() => setForm({ label: "SearXNG", kind: "searxng", enabled: true, is_default: false })}>
            <Plus />
            {t("admin.addSearch")}
          </Button>
      </SectionActions>
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
                        setForm({ id: p.id, label: p.label, kind: p.kind, endpoint: p.endpoint, engines: p.engines, enabled: p.enabled, is_default: p.is_default, key_hint: p.key_hint })
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
        <SectionActions>
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
        </SectionActions>
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
                <TableHead className={right}>{t("usage.searches")}</TableHead>
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
                  <TableCell className={right}>{r.search_calls != null ? n(r.search_calls) : "–"}</TableCell>
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

// The settings sections, each its own address, listed in the settings page's
// own side column.
export const SETTINGS = [
  { id: "users", label: "admin.users", lead: "settings.usersLead", icon: UsersRound, page: Users },
  { id: "models", label: "admin.models", lead: "settings.modelsLead", icon: Bot, page: Models },
  { id: "search", label: "admin.search", lead: "settings.searchLead", icon: SearchIcon, page: Search },
  { id: "limits", label: "admin.limits", lead: "settings.limitsLead", icon: Gauge, page: Limits },
  { id: "usage", label: "admin.usage", lead: "settings.usageLead", icon: ChartColumn, page: Usage },
] as const;

// A section's main action sits beside its title at the top of the page.
function SectionActions({ children }: { children: ReactNode }) {
  return <PortalTo id="settings-actions">{children}</PortalTo>;
}

const FOLDED_KEY = "litstorm.settingsNavFolded";

function readFolded() {
  try {
    return localStorage.getItem(FOLDED_KEY) === "1";
  } catch {
    return false;
  }
}

// A second, narrower side column for the sections, as in the design
// reference; it folds to icons like the main sidebar.
function SettingsNav({ current }: { current: string }) {
  const { t } = useT();
  const [folded, setFolded] = useState(readFolded);
  const toggle = () => {
    setFolded(!folded);
    try {
      localStorage.setItem(FOLDED_KEY, folded ? "0" : "1");
    } catch {
      // Private windows may refuse storage; the column still folds.
    }
  };
  return (
    <nav
      className={cn(
        "sticky top-16 hidden h-[calc(100svh-4rem)] shrink-0 flex-col gap-1.5 overflow-y-auto border-r p-3 transition-[width] duration-200 ease-linear md:flex",
        folded ? "w-[4.25rem]" : "w-60",
      )}
    >
      <div className={cn("mb-1 flex h-8 items-center", folded ? "justify-center" : "justify-between pl-1")}>
        {!folded && (
          <span className="truncate text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t("nav.admin")}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground"
          onClick={toggle}
          aria-label={folded ? t("settings.expand") : t("settings.collapse")}
        >
          {folded ? <PanelLeftOpen /> : <PanelLeftClose />}
        </Button>
      </div>
      {SETTINGS.map((x) => {
        const active = x.id === current;
        const link = (
          <Link
            to="/settings/$section"
            params={{ section: x.id }}
            aria-label={t(x.label)}
            className={cn(
              "flex h-10 items-center gap-3 rounded-lg border px-3 text-sm transition-colors",
              active
                ? "border-transparent bg-muted font-medium"
                : "bg-background text-foreground/85 shadow-xs hover:bg-muted/50",
              folded && "justify-center px-0",
            )}
          >
            <x.icon className="size-4 shrink-0" />
            {!folded && <span className="truncate">{t(x.label)}</span>}
          </Link>
        );
        return folded ? (
          <Tooltip key={x.id}>
            <TooltipTrigger asChild>{link}</TooltipTrigger>
            <TooltipContent side="right">{t(x.label)}</TooltipContent>
          </Tooltip>
        ) : (
          <div key={x.id}>{link}</div>
        );
      })}
    </nav>
  );
}

export function AdminPage() {
  const { t } = useT();
  const { section } = useParams({ from: "/app/settings/$section" });
  const current = SETTINGS.find((s) => s.id === section) ?? SETTINGS[0];
  const Page = current.page;
  return (
    <div className="flex flex-1">
      <SettingsNav current={current.id} />
      <div className="min-w-0 flex-1">
        {/* Phones have no room for the column: the sections become a row. */}
        <div className="flex gap-1.5 overflow-x-auto border-b px-4 py-2 [scrollbar-width:none] md:hidden">
          {SETTINGS.map((x) => (
            <Link
              key={x.id}
              to="/settings/$section"
              params={{ section: x.id }}
              className={cn(
                "flex h-8 shrink-0 items-center gap-2 rounded-lg border px-3 text-sm",
                x.id === current.id ? "border-transparent bg-muted font-medium" : "bg-background shadow-xs",
              )}
            >
              <x.icon className="size-4" />
              {t(x.label)}
            </Link>
          ))}
        </div>
        <div className="mx-auto w-full max-w-5xl px-6 py-8">
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
          <PageHeader
            title={t(current.label)}
            description={t(current.lead)}
            actions={<div id="settings-actions" className="flex items-center gap-2" />}
          />
          {/* Remount per section so its actions portal into the fresh slot. */}
          <Page key={current.id} />
        </div>
      </div>
    </div>
  );
}

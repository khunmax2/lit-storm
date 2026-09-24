import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call, type Schemas } from "../api/client";
import { Button, Card, ErrorText, Field, Input, PageTitle, Select, Spinner, StatusBadge, formatDate } from "../components/ui";
import { useT } from "../i18n";

const LLM_PROVIDERS = ["openrouter", "gemini", "openai", "groq", "openai-compatible"];
const SEARCH_KINDS = ["searxng", "tavily", "arxiv"];

function CopyLink({ link, email }: { link: string; email: string }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-4 rounded-md border border-accent bg-accent-soft p-4 text-sm">
      <p className="mb-2 font-medium">{t("admin.link")}</p>
      <p className="mb-3 text-muted">{t("admin.linkLead", { email })}</p>
      <div className="flex gap-2">
        <Input readOnly value={link} onFocus={(e) => e.target.select()} />
        <Button
          type="button"
          variant="quiet"
          onClick={async () => {
            await navigator.clipboard.writeText(link);
            setCopied(true);
          }}
        >
          {copied ? t("copied") : t("copy")}
        </Button>
      </div>
    </div>
  );
}

// --- test buttons -------------------------------------------------------------

function TestButton({ kind, id }: { kind: "model" | "search"; id: string }) {
  const { t } = useT();
  const test = useMutation({
    mutationFn: () =>
      kind === "model"
        ? call(api.POST("/api/admin/llm-models/{model_id}/test", { params: { path: { model_id: id } } }))
        : call(api.POST("/api/admin/search-providers/{provider_id}/test", { params: { path: { provider_id: id } } })),
  });
  const r = test.data;
  return (
    <span className="flex items-center gap-2">
      {r && (
        <span className={`max-w-xs truncate text-xs ${r.ok ? "text-ok" : "text-bad"}`} title={r.message}>
          {r.ok ? "✓" : "✕"} {r.message} · {r.seconds}s
        </span>
      )}
      <Button variant="quiet" disabled={test.isPending} onClick={() => test.mutate()}>
        {test.isPending ? t("admin.testing") : t("admin.test")}
      </Button>
    </span>
  );
}

// --- users ------------------------------------------------------------------

type User = Schemas["UserOut"];
const OVERRIDES = [
  ["monthly_run_quota", "admin.override.quota"],
  ["max_concurrent_runs", "admin.override.concurrent"],
  ["max_queued_runs", "admin.override.queued"],
] as const;

function Overrides({ user, onSave }: { user: User; onSave: (body: Schemas["UserPatch"]) => void }) {
  const { t } = useT();
  const [values, setValues] = useState(() =>
    Object.fromEntries(OVERRIDES.map(([k]) => [k, user[k] == null ? "" : String(user[k])])),
  );
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(Object.fromEntries(OVERRIDES.map(([k]) => [k, values[k] === "" ? null : Number(values[k])])));
      }}
    >
      {OVERRIDES.map(([key, label]) => (
        <label key={key} className="flex w-24 flex-col gap-1 text-xs text-muted">
          {t(label)}
          <Input
            type="number"
            min={0}
            value={values[key]}
            onChange={(e) => setValues({ ...values, [key]: e.target.value })}
          />
        </label>
      ))}
      <Button variant="quiet">{t("save")}</Button>
    </form>
  );
}

function Users() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => call(api.GET("/api/admin/users")) });
  const [form, setForm] = useState({ email: "", name: "", role: "user" });
  const [issued, setIssued] = useState<{ link: string; email: string } | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });

  const create = useMutation({
    mutationFn: () => call(api.POST("/api/admin/users", { body: form })),
    onSuccess: (r) => {
      setIssued({ link: r.link, email: r.user.email });
      setForm({ email: "", name: "", role: "user" });
      refresh();
    },
  });
  const link = useMutation({
    mutationFn: (id: string) => call(api.POST("/api/admin/users/{user_id}/link", { params: { path: { user_id: id } } })),
    onSuccess: (r) => {
      setIssued({ link: r.link, email: r.user.email });
      refresh();
    },
  });
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["UserPatch"] }) =>
      call(api.PATCH("/api/admin/users/{user_id}", { params: { path: { user_id: id } }, body })),
    onSuccess: refresh,
  });

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <h2 className="mb-4 font-semibold">{t("admin.newUser")}</h2>
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_10rem_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Field label={t("email")}>
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </Field>
          <Field label={t("name")}>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label={t("admin.role")}>
            <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="user">{t("admin.role.user")}</option>
              <option value="admin">{t("admin.role.admin")}</option>
            </Select>
          </Field>
          <Button disabled={create.isPending}>{t("create")}</Button>
        </form>
        <ErrorText error={create.error ?? link.error ?? patch.error} />
        {issued && <CopyLink {...issued} />}
      </Card>

      {users.isLoading && <Spinner />}
      <div className="overflow-x-auto rounded-lg border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-sunk text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2">{t("name")}</th>
              <th className="px-4 py-2">{t("admin.role")}</th>
              <th className="px-4 py-2">{t("admin.thisMonth")}</th>
              <th className="px-4 py-2">{t("admin.hasPassword")}</th>
              <th className="px-4 py-2">{t("admin.active")}</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {users.data?.map((u) => (
              <tr key={u.id} className="align-top">
                <td className="px-4 py-3">
                  <div className="font-medium">{u.name}</div>
                  <div className="text-xs text-muted">
                    {u.email} · {formatDate(u.created_at, lang)}
                  </div>
                </td>
                <td className="px-4 py-3">{u.role === "admin" ? t("admin.role.admin") : t("admin.role.user")}</td>
                <td className="px-4 py-3">
                  <div className="mb-2 whitespace-nowrap">
                    {u.quota_used ?? 0} / {u.quota_limit ?? "–"}
                    {!!u.quota_reserved && (
                      <span className="text-xs text-muted"> · {t("quota.reserved", { reserved: u.quota_reserved })}</span>
                    )}
                  </div>
                  <details>
                    <summary className="cursor-pointer text-xs text-muted">{t("admin.overrides")}</summary>
                    <div className="mt-2">
                      <Overrides user={u} onSave={(body) => patch.mutate({ id: u.id, body })} />
                    </div>
                  </details>
                </td>
                <td className="px-4 py-3">{u.has_password ? t("yes") : t("no")}</td>
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={u.is_active}
                    onChange={(e) => patch.mutate({ id: u.id, body: { is_active: e.target.checked } })}
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    variant="quiet"
                    onClick={() => (!u.has_password || confirm(t("admin.resetConfirm"))) && link.mutate(u.id)}
                  >
                    {t("admin.newLink")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- models -------------------------------------------------------------------

function Keys() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const keys = useQuery({ queryKey: ["admin-keys"], queryFn: () => call(api.GET("/api/admin/llm-credentials")) });
  const [editing, setEditing] = useState<{ provider: string; api_key: string; api_base: string } | null>(null);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/admin/llm-credentials/{provider}", {
          params: { path: { provider: editing!.provider } },
          body: { api_key: editing!.api_key, api_base: editing!.api_base || null },
        }),
      ),
    onSuccess: () => {
      setEditing(null);
      queryClient.invalidateQueries({ queryKey: ["admin-keys"] });
    },
  });
  return (
    <Card>
      <h2 className="mb-4 font-semibold">{t("admin.keys")}</h2>
      <ul className="divide-y divide-line text-sm">
        {keys.data?.map((k) => (
          <li key={k.provider} className="py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="font-medium">{k.provider}</span>
                <span className="ml-3 text-muted">
                  {k.key_hint ? t("admin.keyHint", { hint: k.key_hint }) : t("admin.noKey")}
                </span>
              </div>
              <Button variant="quiet" onClick={() => setEditing({ provider: k.provider, api_key: "", api_base: k.api_base ?? "" })}>
                {t("edit")}
              </Button>
            </div>
            {editing?.provider === k.provider && (
              <form
                className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
                onSubmit={(e) => {
                  e.preventDefault();
                  save.mutate();
                }}
              >
                <Field label={t("admin.apiKey")}>
                  <Input
                    type="password"
                    autoComplete="off"
                    value={editing.api_key}
                    onChange={(e) => setEditing({ ...editing, api_key: e.target.value })}
                    required
                  />
                </Field>
                <Field label={t("admin.apiBase")}>
                  <Input value={editing.api_base} onChange={(e) => setEditing({ ...editing, api_base: e.target.value })} />
                </Field>
                <div className="flex gap-2">
                  <Button disabled={save.isPending}>{t("save")}</Button>
                  <Button type="button" variant="quiet" onClick={() => setEditing(null)}>
                    {t("cancel")}
                  </Button>
                </div>
              </form>
            )}
          </li>
        ))}
      </ul>
      <ErrorText error={save.error} />
    </Card>
  );
}

type ModelForm = Omit<Schemas["ModelIn"], "max_tokens" | "price_in_per_mtok" | "price_out_per_mtok"> & {
  id?: string;
  talk: string;
  write: string;
  priceIn: string;
  priceOut: string;
};

const emptyModel: ModelForm = {
  label: "",
  provider: "openrouter",
  model: "",
  reasoning: "",
  enabled: true,
  is_default: false,
  talk: "",
  write: "",
  priceIn: "",
  priceOut: "",
};

function Models() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: ["admin-models"], queryFn: () => call(api.GET("/api/admin/llm-models")) });
  const [form, setForm] = useState<ModelForm | null>(null);
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
      setForm(null);
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
    },
  });
  const tokens = (m: Schemas["ModelOut"]) => m.max_tokens as { conversation?: number; writing?: number };
  return (
    <div className="flex flex-col gap-6">
      <Keys />
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">{t("admin.models")}</h2>
          <Button variant="quiet" onClick={() => setForm({ ...emptyModel })}>
            {t("admin.addModel")}
          </Button>
        </div>
        <ul className="divide-y divide-line text-sm">
          {models.data?.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-3 py-3">
              <div>
                <span className="font-medium">{m.label}</span>
                {m.is_default && <span className="ml-2 rounded bg-accent-soft px-1.5 text-xs text-accent">{t("admin.default")}</span>}
                {!m.enabled && <span className="ml-2 text-xs text-muted">({t("admin.enabled")}: {t("no")})</span>}
                <div className="text-xs text-muted">
                  {m.provider} · {m.model}
                  {m.reasoning && ` · ${m.reasoning}`}
                </div>
              </div>
              <span className="flex items-center gap-2">
                <TestButton kind="model" id={m.id} />
                <Button
                  variant="quiet"
                  onClick={() =>
                    setForm({
                      ...m,
                      talk: String(tokens(m).conversation ?? ""),
                      write: String(tokens(m).writing ?? ""),
                      priceIn: m.price_in_per_mtok == null ? "" : String(m.price_in_per_mtok),
                      priceOut: m.price_out_per_mtok == null ? "" : String(m.price_out_per_mtok),
                    })
                  }
                >
                  {t("edit")}
                </Button>
              </span>
            </li>
          ))}
        </ul>
        {form && (
          <form
            className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <Field label={t("admin.label")}>
              <Input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} required />
            </Field>
            <Field label={t("admin.provider")}>
              <Select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
                {LLM_PROVIDERS.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </Select>
            </Field>
            <Field label={t("admin.modelId")}>
              <Input
                placeholder="google/gemini-3.5-flash-lite"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
                required
              />
            </Field>
            <Field label={t("admin.reasoning")} hint={t("admin.reasoningHelp")}>
              <Input value={form.reasoning ?? ""} onChange={(e) => setForm({ ...form, reasoning: e.target.value })} />
            </Field>
            <Field label={t("admin.maxTokens")}>
              <div className="flex gap-2">
                <Input type="number" min={100} placeholder="500" value={form.talk} onChange={(e) => setForm({ ...form, talk: e.target.value })} />
                <Input type="number" min={100} placeholder="3000" value={form.write} onChange={(e) => setForm({ ...form, write: e.target.value })} />
              </div>
            </Field>
            <Field label={t("admin.price")} hint={t("admin.priceHelp")}>
              <div className="flex gap-2">
                <Input type="number" min={0} step="any" value={form.priceIn} onChange={(e) => setForm({ ...form, priceIn: e.target.value })} />
                <Input type="number" min={0} step="any" value={form.priceOut} onChange={(e) => setForm({ ...form, priceOut: e.target.value })} />
              </div>
            </Field>
            <div className="flex items-end gap-5 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                {t("admin.enabled")}
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
                {t("admin.default")}
              </label>
            </div>
            <div className="flex gap-2 sm:col-span-2">
              <Button disabled={save.isPending}>{t("save")}</Button>
              <Button type="button" variant="quiet" onClick={() => setForm(null)}>
                {t("cancel")}
              </Button>
            </div>
            <div className="sm:col-span-2">
              <ErrorText error={save.error} />
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}

// --- Search Providers -----------------------------------------------------------

type SearchForm = Schemas["SearchIn"] & { id?: string };

function Search() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const providers = useQuery({ queryKey: ["admin-search"], queryFn: () => call(api.GET("/api/admin/search-providers")) });
  const [form, setForm] = useState<SearchForm | null>(null);
  const save = useMutation({
    mutationFn: () => {
      const { id, ...body } = form!;
      return id
        ? call(api.PUT("/api/admin/search-providers/{provider_id}", { params: { path: { provider_id: id } }, body }))
        : call(api.POST("/api/admin/search-providers", { body }));
    },
    onSuccess: () => {
      setForm(null);
      queryClient.invalidateQueries({ queryKey: ["admin-search"] });
    },
  });
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold">{t("admin.search")}</h2>
        <Button variant="quiet" onClick={() => setForm({ label: "", kind: "searxng", enabled: true, is_default: false })}>
          {t("admin.addSearch")}
        </Button>
      </div>
      <ul className="divide-y divide-line text-sm">
        {providers.data?.map((p) => (
          <li key={p.id} className="flex items-center justify-between gap-3 py-3">
            <div>
              <span className="font-medium">{p.label}</span>
              {p.is_default && <span className="ml-2 rounded bg-accent-soft px-1.5 text-xs text-accent">{t("admin.default")}</span>}
              <div className="text-xs text-muted">
                {p.kind}
                {p.endpoint && ` · ${p.endpoint}`}
                {p.key_hint && ` · ${t("admin.keyHint", { hint: p.key_hint })}`}
              </div>
            </div>
            <span className="flex items-center gap-2">
              <TestButton kind="search" id={p.id} />
              <Button
                variant="quiet"
                onClick={() => setForm({ id: p.id, label: p.label, kind: p.kind, endpoint: p.endpoint, engines: p.engines, enabled: p.enabled, is_default: p.is_default })}
              >
                {t("edit")}
              </Button>
            </span>
          </li>
        ))}
      </ul>
      {form && (
        <form
          className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Field label={t("admin.label")}>
            <Input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} required />
          </Field>
          <Field label={t("admin.kind")}>
            <Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {SEARCH_KINDS.map((k) => (
                <option key={k}>{k}</option>
              ))}
            </Select>
          </Field>
          {form.kind === "searxng" && (
            <>
              <Field label={t("admin.endpoint")}>
                <Input value={form.endpoint ?? ""} onChange={(e) => setForm({ ...form, endpoint: e.target.value })} required />
              </Field>
              <Field label={t("admin.engines")}>
                <Input value={form.engines ?? ""} onChange={(e) => setForm({ ...form, engines: e.target.value })} />
              </Field>
            </>
          )}
          {form.kind === "tavily" && (
            <Field label={t("admin.apiKey")}>
              <Input type="password" autoComplete="off" value={form.api_key ?? ""} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
            </Field>
          )}
          <div className="flex items-end gap-5 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              {t("admin.enabled")}
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
              {t("admin.default")}
            </label>
          </div>
          <div className="flex gap-2 sm:col-span-2">
            <Button disabled={save.isPending}>{t("save")}</Button>
            <Button type="button" variant="quiet" onClick={() => setForm(null)}>
              {t("cancel")}
            </Button>
          </div>
          <div className="sm:col-span-2">
            <ErrorText error={save.error} />
          </div>
        </form>
      )}
    </Card>
  );
}

// --- limits -----------------------------------------------------------------------

function Limits() {
  const { t } = useT();
  const limits = useQuery({ queryKey: ["admin-limits"], queryFn: () => call(api.GET("/api/admin/limits")) });
  const [form, setForm] = useState<Schemas["Limits"] | null>(null);
  const current = form ?? limits.data;
  const save = useMutation({ mutationFn: () => call(api.PUT("/api/admin/limits", { body: current! })) });
  if (!current) return <Spinner />;
  const num = (key: keyof Schemas["Limits"], label: string) => (
    <Field label={label}>
      <Input
        type="number"
        min={0}
        value={String(current[key] ?? "")}
        onChange={(e) => setForm({ ...current, [key]: Number(e.target.value) })}
      />
    </Field>
  );
  return (
    <Card>
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
        <div className="flex items-end gap-3 sm:col-span-2">
          <Button disabled={save.isPending}>{t("save")}</Button>
          {save.isSuccess && <span className="text-sm text-ok">{t("admin.saved")}</span>}
          <ErrorText error={save.error} />
        </div>
      </form>
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
  const runs = useQuery({ queryKey: ["admin-runs"], queryFn: () => call(api.GET("/api/admin/runs", { params: { query: { limit: 50 } } })) });
  const n = (v: number) => v.toLocaleString(lang === "th" ? "th-TH" : "en-GB");
  const cell = "px-3 py-2 text-right tabular-nums";
  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted">{t("usage.privacy")}</p>
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <span className="text-sm">{t("usage.month")}</span>
          <Select className="w-40" value={month} onChange={(e) => setMonth(e.target.value)}>
            {months.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </Select>
        </div>
        {usage.data?.rows.length === 0 && <p className="text-sm text-muted">{t("usage.none")}</p>}
        {!!usage.data?.rows.length && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="px-3 py-2 text-left">{t("usage.user")}</th>
                  <th className={cell}>{t("usage.runs")}</th>
                  <th className={cell}>{t("usage.ok")}</th>
                  <th className={cell}>{t("usage.failed")}</th>
                  <th className={cell}>{t("usage.refunded")}</th>
                  <th className={cell}>{t("usage.tokens")}</th>
                  <th className={cell}>{t("usage.searches")}</th>
                  <th className={cell}>{t("usage.cost")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {usage.data.rows.map((r) => (
                  <tr key={r.user_id}>
                    <td className="px-3 py-2">{r.email}</td>
                    <td className={cell}>{r.runs}</td>
                    <td className={cell}>{r.succeeded}</td>
                    <td className={cell}>{r.failed}</td>
                    <td className={cell}>{r.refunded}</td>
                    <td className={cell}>
                      {n(r.tokens_in)} / {n(r.tokens_out)}
                    </td>
                    <td className={cell}>{r.search_calls}</td>
                    <td className={cell}>
                      {usd(r.cost_usd)}
                      {r.cost_incomplete && <span className="block text-xs text-warn">{t("usage.unknown")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-line font-medium">
                  <td className="px-3 py-2">{t("usage.total")}</td>
                  <td colSpan={6} />
                  <td className={cell}>
                    {usd(usage.data.total_cost_usd)}
                    {usage.data.rows.some((r) => r.cost_incomplete) && (
                      <span className="block text-xs font-normal text-warn">{t("usage.unknown")}</span>
                    )}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>
      <Card>
        <h2 className="mb-3 font-semibold">{t("usage.recent")}</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-line">
              {runs.data?.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-muted">{formatDate(r.queued_at, lang)}</td>
                  <td className="px-3 py-2">{r.email}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-3 py-2 text-xs text-muted">{r.reason && r.reason !== r.status ? r.reason : ""}</td>
                  <td className="px-3 py-2 text-xs">{r.model_label}</td>
                  <td className={cell}>{r.tokens_in != null ? `${n(r.tokens_in)} / ${n(r.tokens_out ?? 0)}` : "–"}</td>
                  <td className={cell}>{usd(r.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export function AdminPage() {
  const { t } = useT();
  const tabs = [
    ["users", t("admin.users")],
    ["models", t("admin.models")],
    ["search", t("admin.search")],
    ["limits", t("admin.limits")],
    ["usage", t("admin.usage")],
  ] as const;
  const [tab, setTab] = useState<(typeof tabs)[number][0]>("users");
  return (
    <>
      <PageTitle>{t("nav.admin")}</PageTitle>
      <div className="mb-6 flex gap-1 border-b border-line">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === key ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "users" && <Users />}
      {tab === "models" && <Models />}
      {tab === "search" && <Search />}
      {tab === "limits" && <Limits />}
      {tab === "usage" && <Usage />}
    </>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent, type ReactNode } from "react";

import { api, call } from "../api/client";
import { Button, Card, ErrorText, Field, Input, Spinner } from "../components/ui";
import { useT } from "../i18n";

function Centered({ title, lead, children }: { title: string; lead?: ReactNode; children: ReactNode }) {
  const { lang, setLang } = useT();
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-between">
          <span className="text-sm font-semibold tracking-wide text-muted">lit-storm</span>
          <button className="text-xs text-muted hover:text-ink" onClick={() => setLang(lang === "th" ? "en" : "th")}>
            {lang === "th" ? "English" : "ไทย"}
          </button>
        </div>
        <Card>
          <h1 className="mb-1 text-xl font-semibold">{title}</h1>
          {lead && <p className="mb-5 text-sm text-muted">{lead}</p>}
          {children}
        </Card>
      </div>
    </div>
  );
}

export function SetupPage() {
  const { t } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["setup"], queryFn: () => call(api.GET("/api/setup")) });
  const [form, setForm] = useState({ code: "", email: "", name: "", password: "" });
  const setup = useMutation({
    mutationFn: () => call(api.POST("/api/setup", { body: form })),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      navigate({ to: "/admin" });
    },
  });
  if (status.isLoading) return <Spinner />;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setup.mutate();
  };
  return (
    <Centered title={t("setup.title")} lead={t("setup.lead")}>
      {status.data && !status.data.code_configured ? (
        <p className="text-sm text-warn">{t("setup.noCode")}</p>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <Field label={t("setup.code")}>
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          </Field>
          <Field label={t("name")}>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label={t("email")}>
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </Field>
          <Field label={t("password")} hint={t("pw.weak")}>
            <Input
              type="password"
              minLength={10}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </Field>
          <ErrorText error={setup.error} />
          <Button disabled={setup.isPending}>{t("setup.submit")}</Button>
        </form>
      )}
    </Centered>
  );
}

export function LoginPage() {
  const { t } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => call(api.POST("/api/auth/login", { body: { email, password } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      navigate({ to: "/" });
    },
  });
  return (
    <Centered title={t("login.title")}>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <Field label={t("email")}>
          <Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label={t("password")}>
          <Input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        {login.error && <p className="text-sm text-bad">{t("login.failed")}</p>}
        <Button disabled={login.isPending}>{t("signIn")}</Button>
      </form>
    </Centered>
  );
}

// The token rides in the URL fragment, which browsers never send to a
// server, so it stays out of access logs and Referer headers.
export function SetPasswordPage() {
  const { t } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const token = window.location.hash.slice(1);
  const [password, setPassword] = useState("");
  const link = useQuery({
    queryKey: ["password-link", token],
    queryFn: () => call(api.POST("/api/auth/password-link", { body: { token, password: "" } })),
    enabled: !!token,
  });
  const save = useMutation({
    mutationFn: () => call(api.POST("/api/auth/password", { body: { token, password } })),
    onSuccess: async () => {
      history.replaceState(null, "", window.location.pathname);
      await queryClient.invalidateQueries();
      navigate({ to: "/" });
    },
  });
  if (link.isLoading) return <Spinner />;
  if (!token || !link.data?.valid) {
    return (
      <Centered title={t("pw.title")}>
        <p className="text-sm text-bad">{t("pw.invalid")}</p>
      </Centered>
    );
  }
  return (
    <Centered title={t("pw.title")} lead={t("pw.lead", { email: link.data.email ?? "" })}>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <input type="email" hidden readOnly autoComplete="username" value={link.data.email ?? ""} />
        <Field label={t("password")}>
          <Input
            type="password"
            minLength={10}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <ErrorText error={save.error} />
        <Button disabled={save.isPending}>{t("pw.submit")}</Button>
      </form>
    </Centered>
  );
}

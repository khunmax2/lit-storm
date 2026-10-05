// Setup, sign-in and set-password: a centred card, as in shadcn's login blocks.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { BookOpenText, Loader2 } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { api, call } from "@/api/client";
import { ErrorText } from "@/components/common";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT } from "@/i18n";

function Centered({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  const { t, lang, setLang } = useT();
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-6">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <BookOpenText className="size-4" />
            </div>
            DeepLit
          </div>
          <Button variant="ghost" size="sm" onClick={() => setLang(lang === "th" ? "en" : "th")}>
            {lang === "th" ? "English" : "ไทย"}
          </Button>
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>
        <p className="text-center text-xs text-muted-foreground">{t("auth.tagline")}</p>
      </div>
    </div>
  );
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
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
      navigate({ to: "/settings/$section", params: { section: "users" } });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setup.mutate();
  };
  return (
    <Centered title={t("setup.title")} description={t("setup.lead")}>
      {status.data && !status.data.code_configured ? (
        <Alert>
          <AlertDescription>{t("setup.noCode")}</AlertDescription>
        </Alert>
      ) : (
        <form className="grid gap-4" onSubmit={submit}>
          <Field id="code" label={t("setup.code")}>
            <Input id="code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          </Field>
          <Field id="name" label={t("name")}>
            <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field id="email" label={t("email")}>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </Field>
          <Field id="password" label={t("password")} hint={t("pw.weak")}>
            <Input
              id="password"
              type="password"
              minLength={10}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </Field>
          {setup.error && <ErrorText error={setup.error} />}
          <Button type="submit" className="w-full" disabled={setup.isPending}>
            {setup.isPending && <Loader2 className="animate-spin" />}
            {t("setup.submit")}
          </Button>
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
        className="grid gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <Field id="email" label={t("email")}>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field id="password" label={t("password")}>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        {login.error && (
          <Alert variant="destructive">
            <AlertDescription>{t("login.failed")}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" className="w-full" disabled={login.isPending}>
          {login.isPending && <Loader2 className="animate-spin" />}
          {t("signIn")}
        </Button>
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
  if (link.isLoading)
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  if (!token || !link.data?.valid) {
    return (
      <Centered title={t("pw.title")}>
        <Alert variant="destructive">
          <AlertDescription>{t("pw.invalid")}</AlertDescription>
        </Alert>
      </Centered>
    );
  }
  return (
    <Centered title={t("pw.title")} description={t("pw.lead", { email: link.data.email ?? "" })}>
      <form
        className="grid gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <input type="email" hidden readOnly autoComplete="username" value={link.data.email ?? ""} />
        <Field id="password" label={t("password")} hint={t("pw.weak")}>
          <Input
            id="password"
            type="password"
            minLength={10}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        {save.error && <ErrorText error={save.error} />}
        <Button type="submit" className="w-full" disabled={save.isPending}>
          {t("pw.submit")}
        </Button>
      </form>
    </Centered>
  );
}

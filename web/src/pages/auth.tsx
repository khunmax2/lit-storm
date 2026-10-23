// Setup, sign-in and set-password: one card in two halves, the owner's design (2026-10-24).
// On the left, what DeepLit is, over a picture; on the right, the form. Below lg the left half
// goes and the logo sits over the form. Accounts come from an Administrator: there is no
// sign-up, no social sign-in, and a forgotten password is a new link from them.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  BookOpen,
  ChartColumn,
  Eye,
  EyeOff,
  FileText,
  Globe,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  PenLine,
  Search,
  User,
  type LucideIcon,
} from "lucide-react";
import { useState, type ComponentProps, type FormEvent, type ReactNode } from "react";

import { api, call } from "@/api/client";
import { BrandLogo } from "@/components/brand";
import { ErrorText } from "@/components/common";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

// What DeepLit does, along the foot of the picture.
const FEATURES: [LucideIcon, string][] = [
  [Search, "research"],
  [FileText, "outline"],
  [PenLine, "writing"],
  [ChartColumn, "analysis"],
  [BookOpen, "reference"],
];

// The logo's own blue and violet.
const GRADIENT = "bg-gradient-to-r from-[#3D8BFA] to-[#8B6CF6]";

function Hero() {
  const { t } = useT();
  return (
    <div className="relative hidden min-h-[640px] flex-col overflow-hidden bg-[linear-gradient(165deg,#dbe8ff_0%,#b9cff7_38%,#8e9ee6_68%,#4d4a9e_100%)] lg:flex">
      <div className="relative z-10 p-12">
        {/* The picture is light in either theme, so "Deep" stays near-black. */}
        <BrandLogo className="h-24 w-fit dark:text-[#0F1A3D]" />
        <h2 className="mt-8 text-2xl leading-snug font-semibold text-balance text-[#14213d]">{t("auth.heroTitle")}</h2>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-[#33415c]">{t("auth.heroLead")}</p>
      </div>
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#1e1b4b]/90 via-[#1e1b4b]/60 to-transparent px-6 pt-20 pb-6">
        <ul className="grid grid-cols-5 divide-x divide-white/20">
          {FEATURES.map(([Icon, key]) => (
            <li key={key} className="flex flex-col items-center gap-1.5 px-2 text-center">
              <span className="flex size-9 items-center justify-center rounded-full bg-white/90 text-[#3D5BE0] shadow-sm">
                <Icon className="size-4" />
              </span>
              <span className="text-sm font-medium text-white">{t(`auth.feature.${key}` as Key)}</span>
              <span className="text-[11px] leading-tight text-white/75">{t(`auth.feature.${key}.lead` as Key)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function AuthShell({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  const { lang, setLang } = useT();
  return (
    <div className="flex min-h-svh items-center justify-center bg-background bg-[radial-gradient(ellipse_at_top_left,rgb(99_102_241/0.14)_0%,transparent_55%),radial-gradient(ellipse_at_bottom_right,rgb(139_92_246/0.12)_0%,transparent_55%)] p-4 sm:p-8">
      <div className="grid w-full max-w-6xl overflow-hidden rounded-3xl border bg-card shadow-xl shadow-indigo-900/10 lg:grid-cols-[1.15fr_1fr]">
        <Hero />
        <div className="relative flex flex-col justify-center px-6 py-14 sm:px-12 lg:py-12">
          <Button
            variant="outline"
            size="sm"
            className="absolute top-5 right-5 rounded-full"
            onClick={() => setLang(lang === "th" ? "en" : "th")}
            aria-label={lang === "th" ? "English" : "ภาษาไทย"}
          >
            <Globe />
            {lang.toUpperCase()}
          </Button>
          <div className="mx-auto w-full max-w-md">
            <BrandLogo className="mb-6 h-20 w-fit lg:hidden" />
            <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
            <p className={cn("w-fit bg-clip-text text-3xl font-semibold tracking-tight text-transparent", GRADIENT)}>
              DeepLit
            </p>
            {description && <p className="mt-3 text-muted-foreground">{description}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </div>
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

/** A tall input with its icon inside; a password one can be shown. */
function IconInput({ icon: Icon, type, ...props }: ComponentProps<"input"> & { icon: LucideIcon }) {
  const { t } = useT();
  const [shown, setShown] = useState(false);
  const secret = type === "password";
  return (
    <div className="relative">
      <Icon className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input {...props} type={secret && shown ? "text" : type} className={cn("h-12 rounded-xl pl-10", secret && "pr-11")} />
      {secret && (
        <button
          type="button"
          className="absolute top-1/2 right-2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
          onClick={() => setShown(!shown)}
          aria-label={shown ? t("auth.hidePassword") : t("auth.showPassword")}
        >
          {shown ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      )}
    </div>
  );
}

function Submit({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <Button
      type="submit"
      disabled={pending}
      className={cn("h-12 w-full rounded-xl text-base text-white shadow-lg shadow-indigo-500/25 hover:opacity-95", GRADIENT)}
    >
      {pending && <Loader2 className="animate-spin" />}
      {children}
      {!pending && <ArrowRight />}
    </Button>
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
    <AuthShell title={t("setup.heading")} description={t("setup.lead")}>
      {status.data && !status.data.code_configured ? (
        <Alert>
          <AlertDescription>{t("setup.noCode")}</AlertDescription>
        </Alert>
      ) : (
        <form className="grid gap-5" onSubmit={submit}>
          <Field id="code" label={t("setup.code")}>
            <IconInput
              id="code"
              icon={KeyRound}
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
            />
          </Field>
          <Field id="name" label={t("name")}>
            <IconInput
              id="name"
              icon={User}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </Field>
          <Field id="email" label={t("email")}>
            <IconInput
              id="email"
              icon={Mail}
              type="email"
              placeholder="name@example.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </Field>
          <Field id="password" label={t("password")} hint={t("pw.weak")}>
            <IconInput
              id="password"
              icon={Lock}
              type="password"
              minLength={10}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </Field>
          {setup.error && <ErrorText error={setup.error} />}
          <Submit pending={setup.isPending}>{t("setup.submit")}</Submit>
        </form>
      )}
    </AuthShell>
  );
}

export function LoginPage() {
  const { t } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [forgot, setForgot] = useState(false);
  const login = useMutation({
    mutationFn: () => call(api.POST("/api/auth/login", { body: { email, password } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      navigate({ to: "/" });
    },
  });
  return (
    <AuthShell title={t("login.heading")} description={t("login.lead")}>
      <form
        className="grid gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <Field id="email" label={t("email")}>
          <IconInput
            id="email"
            icon={Mail}
            type="email"
            autoComplete="username"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <div className="grid gap-2">
          <Field id="password" label={t("password")}>
            <IconInput
              id="password"
              icon={Lock}
              type="password"
              autoComplete="current-password"
              placeholder={t("auth.passwordPlaceholder")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <button
            type="button"
            className="justify-self-end text-sm font-medium text-brand hover:underline"
            onClick={() => setForgot(!forgot)}
            aria-expanded={forgot}
          >
            {t("auth.forgot")}
          </button>
          {/* No email goes out: an Administrator issues a new set-password link (api/admin.reset_link). */}
          {forgot && (
            <p className="rounded-lg bg-brand-soft px-3 py-2 text-sm" role="status">
              {t("auth.forgotLead")}
            </p>
          )}
        </div>
        {login.error && (
          <Alert variant="destructive">
            <AlertDescription>{t("login.failed")}</AlertDescription>
          </Alert>
        )}
        <Submit pending={login.isPending}>{t("signIn")}</Submit>
      </form>
    </AuthShell>
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
      <AuthShell title={t("pw.title")}>
        <Alert variant="destructive">
          <AlertDescription>{t("pw.invalid")}</AlertDescription>
        </Alert>
      </AuthShell>
    );
  }
  return (
    <AuthShell title={t("pw.title")} description={t("pw.lead", { email: link.data.email ?? "" })}>
      <form
        className="grid gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <input type="email" hidden readOnly autoComplete="username" value={link.data.email ?? ""} />
        <Field id="password" label={t("password")} hint={t("pw.weak")}>
          <IconInput
            id="password"
            icon={Lock}
            type="password"
            minLength={10}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        {save.error && <ErrorText error={save.error} />}
        <Submit pending={save.isPending}>{t("pw.submit")}</Submit>
      </form>
    </AuthShell>
  );
}

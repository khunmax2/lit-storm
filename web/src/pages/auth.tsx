// Setup, sign-in and set-password: one card in two halves, as the owner's design has it
// (2026-10-24). On the left, what DeepLit is, over a picture; on the right, the form. Below lg
// the left half goes and the logo sits over the form. Accounts come from an Administrator:
// there is no sign-up, no social sign-in, and a forgotten password is a new link from them.
import "@fontsource/caveat/latin-500.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  BookOpen,
  ChartColumn,
  Check,
  ChevronDown,
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
import { useState, type ComponentProps, type CSSProperties, type FormEvent, type ReactNode } from "react";

import { api, call } from "@/api/client";
import heroUrl from "@/assets/auth-hero.webp";
import iconUrl from "@/assets/deeplit-icon.svg";
import { BrandLockup, BrandLogo } from "@/components/brand";
import { ErrorText } from "@/components/common";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT, type Key, type Lang } from "@/i18n";
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
const BUTTON = "bg-gradient-to-r from-[#3B8CFF] to-[#8C5CF6]";
const VIOLET = "bg-gradient-to-r from-[#6D5CF5] to-[#A78BFA]";

// --- the picture -------------------------------------------------------------------------------

// The owner's picture (logo/S__34324484_0.jpg) is 1280 × 1229. Its box covers the panel from the
// bottom, as object-cover would, but as a box of its own: what sits on the laptop, the mug and
// the books is placed in the picture's pixels and stays there whatever the panel's shape.
const PICTURE_W = 1280;
const PICTURE_H = 1229;
const at = (x: number, y: number): CSSProperties => ({
  left: `${(x / PICTURE_W) * 100}%`,
  top: `${(y / PICTURE_H) * 100}%`,
});
// The book spines, top to bottom, at their middles (measured on a grid, 2026-10-24).
const SPINES: [string, number][] = [
  ["RESEARCH", 737],
  ["ANALYSIS", 790],
  ["WRITING", 843],
  ["KNOWLEDGE", 895],
];

/** A four-pointed star, as the design scatters them. */
function Sparkle({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" className={className} style={style} aria-hidden="true">
      <path d="M12 0C12.9 7.5 16.5 11.1 24 12C16.5 12.9 12.9 16.5 12 24C11.1 16.5 7.5 12.9 0 12C7.5 11.1 11.1 7.5 12 0Z" fill="currentColor" />
    </svg>
  );
}

/** A loose sheet of notes drifting in from the left edge. */
function Sheet({ style }: { style: CSSProperties }) {
  return (
    <div
      aria-hidden="true"
      className="absolute rounded-[2px] bg-white/90 bg-[repeating-linear-gradient(to_bottom,transparent_0_16%,rgb(148_163_184/0.45)_16%_19%)] bg-clip-content p-[0.7cqw] shadow-md"
      style={style}
    />
  );
}

function Picture() {
  const width = `max(100cqw, calc(100cqh * ${PICTURE_W} / ${PICTURE_H}))`;
  return (
    <div
      aria-hidden="true"
      className="absolute bottom-0 [container-type:inline-size]"
      // A narrow panel (lg, not xl) gives up a quarter of the overflow on the left and the rest
      // on the right: the books keep their words, and the mug goes first.
      style={{ width, left: `calc((100cqw - ${width}) * 0.25)`, aspectRatio: `${PICTURE_W} / ${PICTURE_H}` }}
    >
      <img src={heroUrl} alt="" className="size-full" />
      {/* The mark on the laptop's lid, in its silver, and on the mug, in its colours. */}
      <img
        src={iconUrl}
        alt=""
        className="absolute w-[5.6cqw] -translate-1/2 rotate-3 opacity-90 mix-blend-screen grayscale invert"
        style={at(505, 765)}
      />
      <img src={iconUrl} alt="" className="absolute w-[3.4cqw] -translate-1/2 opacity-90" style={at(1094, 842)} />
      {SPINES.map(([word, y]) => (
        <span
          key={word}
          className="absolute -translate-1/2 -rotate-2 text-[1.35cqw] font-medium tracking-[0.12em] text-white/90 [text-shadow:0_1px_2px_rgb(20_20_80/0.5)]"
          style={at(188, y)}
        >
          {word}
        </span>
      ))}
    </div>
  );
}

function Hero() {
  const { t } = useT();
  return (
    <div className="relative hidden overflow-hidden rounded-l-[27px] bg-[linear-gradient(165deg,#dbe8ff_0%,#b9cff7_38%,#8e9ee6_68%,#4d4a9e_100%)] [container-type:size] lg:block">
      <Picture />
      {/* A veil over the sky, so the dark words read on its blue. */}
      <div className="absolute inset-x-0 top-0 h-[58%] bg-gradient-to-b from-white/70 via-white/35 to-transparent" />
      <Sheet style={{ left: "-1.5cqw", top: "9cqh", width: "6cqw", height: "8cqw", rotate: "-32deg" }} />
      <Sheet style={{ left: "-2cqw", top: "19cqh", width: "7.5cqw", height: "9.5cqw", rotate: "-16deg" }} />
      <Sheet style={{ left: "3cqw", top: "32.5cqh", width: "4.5cqw", height: "5cqw", rotate: "28deg" }} />
      {(
        [
          [6.4, 6, 1.6],
          [7.4, 20, 1],
          [9.8, 30.5, 2.8],
          [92, 11, 1.2],
        ] as const
      ).map(([x, y, size], i) => (
        <Sparkle
          key={i}
          className="absolute text-white [filter:drop-shadow(0_0_6px_rgb(255_255_255/0.9))]"
          style={{ left: `${x}cqw`, top: `${y}cqh`, width: `${size}cqw` }}
        />
      ))}
      <div className="relative" style={{ padding: "8cqw 8cqw 0 18.5cqw" }}>
        <BrandLockup size="clamp(64px, 12.7cqw, 128px)" />
        <h2
          className="font-semibold text-balance text-[#14213d]"
          style={{ marginTop: "4.6cqw", fontSize: "clamp(18px, 2.95cqw, 30px)", lineHeight: 1.35 }}
        >
          {t("auth.heroTitle")}
        </h2>
        <p className="text-[#33415c]" style={{ marginTop: "1.8cqw", maxWidth: "52cqw", fontSize: "clamp(13px, 2cqw, 19px)", lineHeight: 1.6 }}>
          {t("auth.heroLead")}
        </p>
      </div>
      {/* Handwritten, as on a note left on the desk. */}
      <div
        aria-hidden="true"
        className="absolute -rotate-[14deg] text-white/95 [text-shadow:0_1px_3px_rgb(40_40_110/0.35)]"
        style={{ left: "80.5cqw", top: "32cqh", fontFamily: "Caveat, cursive", fontWeight: 500, fontSize: "3.4cqw", lineHeight: 1.05 }}
      >
        <div>Better</div>
        <div className="pl-[0.3em]">Research</div>
        <div className="pl-[0.6em]">Bigger</div>
        <div className="pl-[1.3em]">Ideas</div>
        <svg viewBox="0 0 100 12" className="ml-[0.6em] w-[2.6em]" aria-hidden="true">
          <path d="M2 10C30 4 60 2 98 2" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" />
        </svg>
      </div>
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#26286b]/90 via-[#34368a]/55 to-transparent px-[3cqw] pt-[12cqw] pb-[3.2cqw]">
        <ul className="grid grid-cols-5 divide-x divide-white/25">
          {FEATURES.map(([Icon, key]) => (
            <li key={key} className="flex flex-col items-center gap-1.5 px-2 text-center">
              <span className="flex size-[clamp(30px,4.6cqw,40px)] items-center justify-center rounded-full bg-white/95 text-[#5468F0] shadow-sm">
                <Icon className="size-[55%]" />
              </span>
              <span className="font-medium text-white" style={{ fontSize: "clamp(13px, 1.95cqw, 17px)" }}>
                {t(`auth.feature.${key}` as Key)}
              </span>
              <span className="leading-tight whitespace-pre-line text-white/80" style={{ fontSize: "clamp(10px, 1.5cqw, 13px)" }}>
                {t(`auth.feature.${key}.lead` as Key)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// --- the form's half ----------------------------------------------------------------------------

function LanguageMenu() {
  const { lang, setLang } = useT();
  const names: [Lang, string][] = [
    ["th", "ไทย"],
    ["en", "English"],
  ];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="absolute top-6 right-6 z-10 h-9 gap-1.5 rounded-xl bg-background/90 px-3 shadow-sm lg:right-[7%]">
          <Globe />
          {lang.toUpperCase()}
          <ChevronDown className="opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {names.map(([code, name]) => (
          <DropdownMenuItem key={code} onClick={() => setLang(code)}>
            {name}
            {lang === code && <Check className="ml-auto" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Soft waves in a corner, as on the design's paper. */
function Waves({ className, flip = false }: { className?: string; flip?: boolean }) {
  return (
    <svg
      viewBox="0 0 560 760"
      preserveAspectRatio="none"
      className={cn("pointer-events-none absolute inset-0 size-full", flip && "-scale-x-100", className)}
      aria-hidden="true"
    >
      <path d="M300 0C390 40 450 110 560 150V0Z" fill="currentColor" opacity="0.55" />
      <path d="M400 0C460 30 505 66 560 78V0Z" fill="currentColor" opacity="0.7" />
      <path d="M0 650C130 600 290 720 560 610V760H0Z" fill="currentColor" opacity="0.45" />
      <path d="M190 760C290 700 420 690 560 640V760Z" fill="currentColor" opacity="0.65" />
    </svg>
  );
}

function AuthShell({
  title,
  description,
  footer,
  children,
}: {
  title: string;
  description?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[#eef1fb] p-4 sm:p-8 lg:px-[6vw] dark:bg-background">
      <svg
        viewBox="0 0 1536 1024"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 size-full text-white dark:text-white/[0.03]"
        aria-hidden="true"
      >
        <path d="M0 120C300 40 520 160 820 90C1080 30 1280 0 1536 60V0H0Z" fill="currentColor" opacity="0.7" />
        <path d="M900 1024C1100 900 1300 930 1536 820V1024Z" fill="currentColor" opacity="0.55" />
        <path d="M0 900C200 860 380 960 620 1024H0Z" fill="currentColor" opacity="0.5" />
      </svg>
      <div className="relative grid w-full max-w-[1500px] rounded-[28px] border border-white/70 bg-card shadow-[0_30px_80px_-24px_rgb(55_65_150/0.3)] lg:min-h-[min(50vw,850px)] lg:grid-cols-[58fr_42fr] dark:border-border">
        <Hero />
        <div className="relative flex flex-col overflow-hidden rounded-[27px] bg-gradient-to-br from-white lg:rounded-l-none to-[#f2f4ff] px-6 py-16 sm:px-12 lg:pt-[13%] lg:pr-[9.4%] lg:pb-[10%] lg:pl-[11.4%] dark:from-card dark:to-card">
          <Waves className="text-[#d9e0ff] dark:text-white/[0.03]" />
          <Sparkle className="absolute top-[16%] right-[8%] hidden size-7 text-[#9db0ff] lg:block" />
          <LanguageMenu />
          <div className="relative mx-auto flex w-full max-w-md flex-1 flex-col lg:mx-0 lg:max-w-none">
            <BrandLogo className="mb-6 h-20 w-fit lg:hidden" />
            <h1 className="text-[2.5rem] leading-tight font-semibold tracking-tight text-[#1b1f4b] dark:text-foreground">
              {title}
            </h1>
            <p className={cn("w-fit bg-clip-text text-[2.1rem] leading-tight font-medium text-transparent", VIOLET)}>DeepLit</p>
            {description && (
              <p className="mt-4 max-w-[21rem] text-[1.05rem] leading-relaxed whitespace-pre-line text-[#4a5578] dark:text-muted-foreground">
                {description}
              </p>
            )}
            <div className="mt-8">{children}</div>
            {footer && <div className="mt-auto pt-10">{footer}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-2.5">
      <Label htmlFor={id} className="text-base font-medium text-[#1b2450] dark:text-foreground">
        {label}
      </Label>
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
      <Icon className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-[#3f4a75] dark:text-muted-foreground" />
      <Input
        {...props}
        type={secret && shown ? "text" : type}
        className={cn(
          "h-[3.4rem] rounded-xl border-[#dde2f2] bg-white/90 pl-12 text-base placeholder:text-[#9aa3bf] md:text-base dark:border-input dark:bg-input/30",
          secret && "pr-12",
        )}
      />
      {secret && (
        <button
          type="button"
          className="absolute top-1/2 right-2.5 flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-[#3f4a75] hover:text-foreground dark:text-muted-foreground"
          onClick={() => setShown(!shown)}
          aria-label={shown ? t("auth.hidePassword") : t("auth.showPassword")}
        >
          {/* As the design draws it: crossed out while hidden. */}
          {shown ? <Eye className="size-5" /> : <EyeOff className="size-5" />}
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
      className={cn(
        "h-[3.4rem] w-full rounded-xl text-lg font-medium text-white shadow-lg shadow-indigo-500/20 hover:opacity-95",
        BUTTON,
      )}
    >
      {pending && <Loader2 className="animate-spin" />}
      {children}
      {!pending && <ArrowRight className="size-5" />}
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
    <AuthShell
      title={t("login.heading")}
      description={t("login.lead")}
      footer={
        // Where the design asks people to sign up: accounts here come from an Administrator.
        <p className="text-center text-sm text-muted-foreground">
          {t("auth.noAccount")} <span className="font-medium text-[#2F6BF0] dark:text-brand">{t("auth.askAdmin")}</span>
        </p>
      }
    >
      <form
        className="grid gap-6"
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
            className="mt-1 justify-self-end text-sm text-[#2F6BF0] hover:underline dark:text-brand"
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

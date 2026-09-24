// Small building blocks in one place, shadcn-style: plain components over
// Tailwind with the tokens from styles.css.
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { ApiError } from "../api/client";
import { has, useT } from "../i18n";

function cx(...parts: (string | false | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "danger" };

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md px-3.5 py-2 text-sm font-medium transition",
        "disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        variant === "primary" && "bg-accent text-accent-ink hover:opacity-90",
        variant === "quiet" && "border border-line bg-surface text-ink hover:bg-sunk",
        variant === "danger" && "border border-line bg-surface text-bad hover:bg-bad-soft",
        className,
      )}
    />
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

const control =
  "w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:outline-2 focus:outline-accent";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(control, props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(control, props.className)} />;
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("rounded-lg border border-line bg-surface p-5", className)}>{children}</div>;
}

export function PageTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">{children}</h1>
      {action}
    </div>
  );
}

const tone: Record<string, string> = {
  queued: "bg-sunk text-muted",
  needs_selection: "bg-warn-soft text-warn",
  running: "bg-accent-soft text-accent",
  cancelling: "bg-warn-soft text-warn",
  succeeded: "bg-ok-soft text-ok",
  failed: "bg-bad-soft text-bad",
  cancelled: "bg-sunk text-muted",
  interrupted: "bg-bad-soft text-bad",
};

export function StatusBadge({ status }: { status: string }) {
  const { t } = useT();
  const key = `status.${status}`;
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", tone[status])}>
      {(status === "running" || status === "cancelling") && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {has(key) ? t(key) : status}
    </span>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useT();
  if (!error) return null;
  const code = error instanceof ApiError ? `error.${error.code}` : "";
  return <p className="text-sm text-bad">{has(code) ? t(code) : t("error.generic")}</p>;
}

export function Spinner() {
  const { t } = useT();
  return <p className="text-sm text-muted">{t("loading")}</p>;
}

export function formatDate(iso: string | null | undefined, lang: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(lang === "th" ? "th-TH" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

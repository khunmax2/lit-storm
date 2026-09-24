// Small shared pieces built on shadcn/ui: status badges, errors, page headers.
import { AlertCircle, CheckCircle2, CircleDashed, Clock, Loader2, PauseCircle, XCircle } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ApiError } from "@/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { has, useT } from "@/i18n";
import { cn } from "@/lib/utils";

const STATUS: Record<string, { icon: typeof Clock; className: string; spin?: boolean }> = {
  queued: { icon: Clock, className: "bg-muted text-muted-foreground" },
  needs_selection: { icon: PauseCircle, className: "bg-warning-soft text-warning" },
  running: { icon: Loader2, className: "bg-brand-soft text-brand", spin: true },
  cancelling: { icon: Loader2, className: "bg-warning-soft text-warning", spin: true },
  succeeded: { icon: CheckCircle2, className: "bg-success-soft text-success" },
  failed: { icon: XCircle, className: "bg-destructive/10 text-destructive" },
  cancelled: { icon: CircleDashed, className: "bg-muted text-muted-foreground" },
  interrupted: { icon: AlertCircle, className: "bg-destructive/10 text-destructive" },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const { t } = useT();
  const s = STATUS[status] ?? STATUS.queued;
  const Icon = s.icon;
  const key = `status.${status}`;
  return (
    <Badge variant="secondary" className={cn("gap-1 border-0 font-medium", s.className, className)}>
      <Icon className={cn("size-3", s.spin && "animate-spin")} />
      {has(key) ? t(key) : status}
    </Badge>
  );
}

export function errorMessage(error: unknown, t: ReturnType<typeof useT>["t"]) {
  const code = error instanceof ApiError ? `error.${error.code}` : "";
  return has(code) ? t(code) : t("error.generic");
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useT();
  if (!error) return null;
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertDescription>{errorMessage(error, t)}</AlertDescription>
    </Alert>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 space-y-1">
        {eyebrow && <div className="text-sm text-muted-foreground">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        {description && <p className="text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-xl" />
      ))}
    </div>
  );
}

export function formatDate(iso: string | null | undefined, lang: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(lang === "th" ? "th-TH" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function timeAgo(iso: string, lang: string) {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang === "th" ? "th" : "en", { numeric: "auto" });
  const steps: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [3600, "minute"],
    [86400, "hour"],
    [604800, "day"],
  ];
  let unit: Intl.RelativeTimeFormatUnit = "week";
  let value = seconds / 604800;
  for (let i = 0; i < steps.length; i++) {
    if (seconds < steps[i][0]) {
      unit = steps[i][1];
      value = seconds / (i === 0 ? 1 : steps[i - 1][0]);
      break;
    }
  }
  return rtf.format(-Math.round(value), unit);
}

export function domainOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Put page-specific content (breadcrumbs, actions) in the app's top bar. */
export function Toolbar({ children }: { children: ReactNode }) {
  const [el, setEl] = useState<HTMLElement | null>(null);
  useEffect(() => setEl(document.getElementById("page-toolbar")), []);
  return el ? createPortal(children, el) : null;
}

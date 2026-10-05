// API tokens for the MCP server (server: api/tokens.py): a table of them, the dialog that makes one, and the
// token shown the one time it can be.
import { useMutation } from "@tanstack/react-query";
import { Check, Copy, KeyRound, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { type Schemas } from "@/api/client";
import { ErrorText, timeAgo } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

export type Token = Schemas["TokenOut"];
export type NewToken = Schemas["NewTokenOut"];
export type TokenBody = { name: string; scopes: string[]; days: number | null };

export const SCOPES = ["read", "research"] as const;
const LIFETIMES = [30, 90, 365];

export function CopyField({ value, mono = true }: { value: string; mono?: boolean }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex gap-2">
      <Input readOnly value={value} onFocus={(e) => e.target.select()} className={cn("bg-background text-xs", mono && "font-mono")} />
      <Button
        type="button"
        variant="outline"
        onClick={async () => {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          toast.success(t("copied"));
        }}
      >
        {copied ? <Check /> : <Copy />}
        {copied ? t("copied") : t("copy")}
      </Button>
    </div>
  );
}

/** The token, this once. Below it, whatever helps put it to use (the setup snippets). */
export function ShownToken({ made, children }: { made: NewToken; children?: ReactNode }) {
  const { t } = useT();
  return (
    <div className="grid min-w-0 gap-3 rounded-lg border border-brand/30 bg-brand-soft/40 p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <KeyRound className="size-4 text-brand" />
        {t("tokens.shownOnce", { name: made.record.name })}
      </div>
      <CopyField value={made.token} />
      {children}
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const { t } = useT();
  return (
    <Badge variant={state === "live" ? "secondary" : "outline"} className={cn(state !== "live" && "text-muted-foreground")}>
      {t(`tokens.state.${state}` as Key)}
    </Badge>
  );
}

export function TokenTable({
  rows,
  onRevoke,
  showOwner = false,
}: {
  rows: Token[];
  onRevoke: (t: Token) => void;
  showOwner?: boolean;
}) {
  const { t, lang } = useT();
  if (!rows.length) return <p className="py-6 text-center text-sm text-muted-foreground">{t("tokens.none")}</p>;
  return (
    <div className="overflow-x-auto rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("tokens.name")}</TableHead>
            {showOwner && <TableHead>{t("tokens.owner")}</TableHead>}
            <TableHead>{t("tokens.scopes")}</TableHead>
            <TableHead>{t("tokens.expires")}</TableHead>
            <TableHead>{t("tokens.lastUsed")}</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id} className={cn(r.state !== "live" && "opacity-60")}>
              <TableCell>
                <div className="font-medium">{r.name}</div>
                <div className="font-mono text-xs text-muted-foreground">{r.prefix}…</div>
              </TableCell>
              {showOwner && (
                <TableCell className="text-sm">
                  {r.owner_name}
                  {r.owner_kind === "integration" && <span className="ml-1 text-xs text-muted-foreground">({t("tokens.integration")})</span>}
                </TableCell>
              )}
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {r.scopes.map((s) => (
                    <Badge key={s} variant="outline">
                      {t(`tokens.scope.${s}` as Key)}
                    </Badge>
                  ))}
                </div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {r.state === "live" ? (r.expires_at ? new Date(r.expires_at).toLocaleDateString(lang) : t("tokens.never")) : <StateBadge state={r.state} />}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">{r.last_used_at ? timeAgo(r.last_used_at, lang) : t("tokens.unused")}</TableCell>
              <TableCell className="text-right">
                {r.state === "live" && (
                  <Button variant="ghost" size="sm" onClick={() => onRevoke(r)} aria-label={t("tokens.revoke")}>
                    <Trash2 />
                    <span className="hidden sm:inline">{t("tokens.revoke")}</span>
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/** Make a token: a name, what it may do, how long it lives. Shows the token once made. */
export function NewTokenDialog({
  open,
  onOpenChange,
  make,
  allowForever = false,
  after,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  make: (body: TokenBody) => Promise<NewToken>;
  allowForever?: boolean;
  after?: (made: NewToken) => ReactNode;
}) {
  const { t } = useT();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>([...SCOPES]);
  const [days, setDays] = useState(allowForever ? "never" : "90");
  const [made, setMade] = useState<NewToken | null>(null);
  const create = useMutation({
    mutationFn: () => make({ name: name.trim(), scopes, days: days === "never" ? null : Number(days) }),
    onSuccess: setMade,
  });
  const close = (o: boolean) => {
    if (!o) {
      setName("");
      setScopes([...SCOPES]);
      setMade(null);
      create.reset();
    }
    onOpenChange(o);
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("tokens.new")}</DialogTitle>
          <DialogDescription>{t("tokens.newLead")}</DialogDescription>
        </DialogHeader>
        {made ? (
          <ShownToken made={made}>{after?.(made)}</ShownToken>
        ) : (
          <form
            id="new-token"
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim() && scopes.length) create.mutate();
            }}
          >
            <div className="grid gap-1.5">
              <Label htmlFor="token-name">{t("tokens.name")}</Label>
              <Input id="token-name" value={name} onChange={(e) => setName(e.target.value)} placeholder={t("tokens.namePlaceholder")} autoFocus />
            </div>
            <div className="grid gap-2">
              <Label>{t("tokens.scopes")}</Label>
              {SCOPES.map((s) => (
                <label key={s} className="flex cursor-pointer items-start gap-2.5 text-sm">
                  <Checkbox
                    checked={scopes.includes(s)}
                    onCheckedChange={(on) => setScopes(on ? [...new Set([...scopes, s])] : scopes.filter((x) => x !== s))}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">{t(`tokens.scope.${s}` as Key)}</span>
                    <span className="block text-xs text-muted-foreground">{t(`tokens.scopeLead.${s}` as Key)}</span>
                  </span>
                </label>
              ))}
            </div>
            <div className="grid gap-1.5">
              <Label>{t("tokens.lifetime")}</Label>
              <Select value={days} onValueChange={setDays}>
                <SelectTrigger className="w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LIFETIMES.map((d) => (
                    <SelectItem key={d} value={String(d)}>
                      {t("tokens.days", { n: d })}
                    </SelectItem>
                  ))}
                  {allowForever && <SelectItem value="never">{t("tokens.never")}</SelectItem>}
                </SelectContent>
              </Select>
            </div>
            <ErrorText error={create.error} />
          </form>
        )}
        <DialogFooter>
          {made ? (
            <Button onClick={() => close(false)}>{t("common.done")}</Button>
          ) : (
            <Button type="submit" form="new-token" disabled={!name.trim() || !scopes.length || create.isPending}>
              {t("tokens.create")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

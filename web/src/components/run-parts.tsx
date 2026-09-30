// Pieces of a Run's card that a Discussion's Turns use too: the stepper,
// the notes on how it went, and the confirm dialog.
import { Check, Circle, History, Info, Loader2, Timer } from "lucide-react";
import { useState } from "react";

import { useRunOptions } from "@/components/composer";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

export const FINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
// STORM's stages; every Engine's own list comes with the options.
const DEFAULT_STAGES = ["research", "outline", "article", "polish"];

/** Ask before doing something that cannot be undone from this page. */
export function useConfirm() {
  const { t } = useT();
  const [state, setState] = useState<{ text: string; action: () => void } | null>(null);
  const dialog = (
    <AlertDialog open={!!state} onOpenChange={(open) => !open && setState(null)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("common.confirm")}</AlertDialogTitle>
          <AlertDialogDescription>{state?.text}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              state?.action();
              setState(null);
            }}
          >
            {t("yes")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
  return { confirm: (text: string, action: () => void) => setState({ text, action }), dialog };
}

export function Stepper({ stage, status, engine }: { stage: string | null; status: string; engine: string }) {
  const { t } = useT();
  const STAGES = useRunOptions().data?.engines.find((e) => e.id === engine)?.stages ?? DEFAULT_STAGES;
  const current = STAGES.indexOf(stage ?? "");
  const done = status === "succeeded";
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-xs">
      {STAGES.map((s, i) => {
        const state = done || i < current ? "done" : i === current ? "now" : "todo";
        return (
          <li key={s} className="flex items-center gap-2">
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full px-2.5 py-1",
                state === "done" && "bg-success-soft text-success",
                state === "now" && "bg-brand-soft font-medium text-brand",
                state === "todo" && "bg-muted text-muted-foreground",
              )}
            >
              {state === "done" ? (
                <Check className="size-3" />
              ) : state === "now" ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Circle className="size-3" />
              )}
              {t(`stage.${s}` as Key)}
            </span>
            {i < STAGES.length - 1 && <span className="h-px w-3 bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}

// How a Run went, where the owner should know: it wrote from what it had
// when its time ran short, or matched sources with the fallback model.
// Cached searches are good news, said quietly.
export function RunNotes({ notes }: { notes: Record<string, unknown> }) {
  const { t } = useT();
  const cut = notes.research_cut_short as { seconds?: number } | undefined;
  const fallback = notes.embedding as { fallback?: boolean } | undefined;
  const cache = notes.search_cache as { hits?: number } | undefined;
  const skipped = Object.keys((notes.sources_skipped as { sources?: Record<string, string> } | undefined)?.sources ?? {});
  if (!cut && !fallback?.fallback && !cache?.hits && !skipped.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      {cut && (
        <span className="flex items-center gap-1 text-warning">
          <Timer className="size-3" />
          {t("run.note.cutShort", { n: Math.round((cut.seconds ?? 0) / 60) || 1 })}
        </span>
      )}
      {skipped.length > 0 && (
        <span className="flex items-center gap-1 text-warning">
          <Info className="size-3" />
          {t("run.note.sourcesSkipped", { names: skipped.join(", ") })}
        </span>
      )}
      {fallback?.fallback && (
        <span className="flex items-center gap-1 text-warning">
          <Info className="size-3" />
          {t("run.note.embeddingFallback")}
        </span>
      )}
      {!!cache?.hits && (
        <span className="flex items-center gap-1 text-muted-foreground">
          <History className="size-3" />
          {t("run.note.cached", { n: cache.hits })}
        </span>
      )}
    </div>
  );
}

// A segmented control whose white pill slides to the chosen option, inset
// in a grey track so a rim of grey shows around it (the reference design).
import { useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** `hint` explains the option when the pointer rests on it a moment. */
export type Segment<T extends string> = { value: T; label: ReactNode; hint?: ReactNode };

// Long enough that sweeping across the options does not flash every hint.
const HINT_DELAY = 600;

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: readonly Segment<T>[];
  /** What the choice is about, for screen readers. */
  label: string;
  className?: string;
}) {
  const track = useRef<HTMLDivElement>(null);
  const [pill, setPill] = useState<{ left: number; width: number } | null>(null);
  // The first placement is instant; only later changes slide.
  const [animate, setAnimate] = useState(false);

  useLayoutEffect(() => {
    const el = track.current;
    if (!el) return;
    const place = () => {
      const active = el.querySelector<HTMLElement>('[aria-selected="true"]');
      if (active) setPill({ left: active.offsetLeft, width: active.offsetWidth });
    };
    place();
    // Web fonts arriving late change the labels' widths.
    const observer = new ResizeObserver(place);
    observer.observe(el);
    return () => observer.disconnect();
  }, [value, options]);

  useLayoutEffect(() => {
    if (pill && !animate) requestAnimationFrame(() => setAnimate(true));
  }, [pill, animate]);

  const onKeyDown = (e: KeyboardEvent) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const i = options.findIndex((o) => o.value === value);
    const next = options[(i + step + options.length) % options.length];
    onChange(next.value);
    track.current?.querySelector<HTMLElement>(`[data-value="${next.value}"]`)?.focus();
  };

  return (
    <div
      ref={track}
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn("relative inline-flex items-center rounded-xl bg-muted p-1 dark:bg-muted/60", className)}
    >
      {pill && (
        <span
          aria-hidden
          className={cn(
            "absolute top-1 bottom-1 rounded-lg bg-background shadow-sm ring-1 ring-black/5 dark:bg-card dark:ring-white/10",
            animate && "transition-[left,width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none",
          )}
          style={{ left: pill.left, width: pill.width }}
        />
      )}
      {options.map((o) => {
        const active = o.value === value;
        const button = (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            data-value={o.value}
            onClick={() => onChange(o.value)}
            className={cn(
              "relative z-10 inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-4 text-sm whitespace-nowrap transition-colors duration-200 outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        );
        if (!o.hint) return button;
        return (
          <Tooltip key={o.value} delayDuration={HINT_DELAY}>
            <TooltipTrigger asChild>{button}</TooltipTrigger>
            <TooltipContent side="bottom" sideOffset={8} className="max-w-xs px-3.5 py-3 text-left">
              {o.hint}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}

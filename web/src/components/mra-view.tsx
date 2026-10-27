import "@fontsource-variable/anuphan";
import "@fontsource/bai-jamjuree/500.css";
import "@fontsource/bai-jamjuree/600.css";
import "@fontsource/bai-jamjuree/700.css";
import "@fontsource-variable/martian-mono/standard.css";
import "@fontsource-variable/source-serif-4/opsz.css";
import "@fontsource-variable/source-serif-4/opsz-italic.css";

import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { ApiError, api, call } from "@/api/client";
import { ErrorText, LoadingRows } from "@/components/common";
import { QuickAnswer } from "@mra/components/review/quick-answer";
import { Report } from "@mra/components/review/report";
import { host } from "@mra/lib/host";
import { isQuickReview } from "@mra/lib/quick";
import type { Review } from "@mra/lib/types";
import css from "@mra/report.css?inline";

// Tailwind's @property rules do nothing inside a shadow root; they go to the
// document once (the same declarations DeepLit's own stylesheet makes).
const PROPERTY = /@property\s+[^{]+\{[^}]*\}/g;
let hoisted = false;
function hoistProperties() {
  if (hoisted) return;
  hoisted = true;
  const style = document.createElement("style");
  style.dataset.mra = "properties";
  style.textContent = (css.match(PROPERTY) ?? []).join("\n");
  document.head.append(style);
}

/** MedicalReviewerAgent's own report, drawn here from the review kept with
 *  the Run (MRA's report code, src/mra), in a shadow root so its stylesheet
 *  and DeepLit's never meet. `onMissing`: the Run has no review kept. */
export function MraView({ runId, onMissing }: { runId: string; onMissing: () => void }) {
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";
  const box = useRef<HTMLDivElement>(null);
  const [root, setRoot] = useState<ShadowRoot | null>(null);
  const review = useQuery({
    queryKey: ["service-data", runId],
    queryFn: () =>
      call(api.GET("/api/runs/{run_id}/service-data", { params: { path: { run_id: runId } } })) as Promise<Review>,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
  const missing = review.error instanceof ApiError && review.error.status === 404;

  useEffect(() => {
    if (missing) onMissing();
  }, [missing, onMissing]);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    hoistProperties();
    const shadow = el.shadowRoot ?? el.attachShadow({ mode: "open" });
    if (!shadow.querySelector("style[data-mra]")) {
      const style = document.createElement("style");
      style.dataset.mra = "report";
      style.textContent = css.replace(PROPERTY, "");
      shadow.append(style);
    }
    host.root = shadow;
    host.el = el;
    // The browser looks for "#id" in the document, not in a shadow root: the
    // report's in-page links (contents, references) are followed here.
    const follow = (e: Event) => {
      const a = (e.target as Element | null)?.closest?.("a[href^='#']");
      const id = a?.getAttribute("href")?.slice(1);
      const target = id ? shadow.getElementById(decodeURIComponent(id)) : null;
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    };
    shadow.addEventListener("click", follow);
    setRoot(shadow);
    return () => {
      shadow.removeEventListener("click", follow);
      host.root = document;
      host.el = null;
    };
  }, []);

  // The app's theme switch drives the report's; its charts read their
  // colours again on MRA's own theme event.
  useLayoutEffect(() => {
    window.dispatchEvent(new Event("themechange"));
  }, [theme]);

  return (
    <>
      {review.error && !missing && <ErrorText error={review.error} />}
      {review.isLoading && <LoadingRows rows={6} />}
      <div
        ref={box}
        data-theme={theme}
        data-mra-report
        // Under DeepLit's sticky header: MRA's in-page links stop below it.
        style={{ ["--mra-header-h" as string]: "4rem" }}
      >
        {root &&
          review.data &&
          createPortal(
            isQuickReview(review.data) ? (
              // MRA's "run a full review" opens MRA's own form, which DeepLit does not have.
              <QuickAnswer review={review.data} upgrade={false} />
            ) : (
              <Report review={review.data} offline />
            ),
            root,
          )}
      </div>
    </>
  );
}

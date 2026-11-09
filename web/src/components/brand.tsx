// DeepLit's mark: the icon (the sidebar, the favicon), the full logo, the icon over the wordmark
// (the sign-in form on a phone), and the lockup, the icon beside the wordmark with "Deep
// Literature" under it (the sign-in picture). Drawn by the owner, 2026-10-23.
import { useId } from "react";

import iconUrl from "@/assets/deeplit-icon.svg";
import logoRaw from "@/assets/deeplit-logo.svg?raw";
import { cn } from "@/lib/utils";

// "Deep" is drawn in near-black (#0F1A3D), which a dark theme would swallow: it takes the text
// colour instead, that same near-black on a light theme.
const LOGO = logoRaw.replace('fill="#0F1A3D"', 'fill="currentColor"');
// The icon's shapes come first, then the wordmark's, which begins with "Deep" in currentColor.
// Where each lies in the logo's own units (measured with getBBox, 2026-10-24); the icon reaches
// down past the wordmark's top, so each part is drawn without the other's shapes.
const SPLIT = LOGO.indexOf('<path fill="currentColor"');
const DEFS_END = LOGO.indexOf("</defs>") + "</defs>".length;
const PARTS = {
  whole: { viewBox: "230 110 767 670", svg: LOGO },
  icon: { viewBox: "366 133 533 392", svg: LOGO.slice(0, SPLIT) + "</svg>" },
  wordmark: { viewBox: "264 512 698 243", svg: LOGO.slice(0, DEFS_END) + LOGO.slice(SPLIT) },
};

/** A part of the logo as markup. Each copy names its gradients for itself: with two on a page
 * and the first one hidden (the sign-in picture, below lg), url(#id) finds the hidden one's and
 * draws nothing. */
function drawn(part: keyof typeof PARTS, own: string, label?: string) {
  const { viewBox, svg } = PARTS[part];
  const named = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"';
  return svg
    .replace(/viewBox="[^"]*" width="\d+" height="\d+"/, `viewBox="${viewBox}" class="h-full w-auto" ${named}`)
    .replace(/id="([\w-]+)"/g, `id="$1-${own}"`)
    .replace(/url\(#([\w-]+)\)/g, `url(#$1-${own})`);
}

function useOwn() {
  return useId().replace(/[^\w-]/g, "");
}

export function BrandIcon({ className }: { className?: string }) {
  return <img src={iconUrl} alt="" className={cn("shrink-0", className)} />;
}

export function BrandLogo({ className }: { className?: string }) {
  const own = useOwn();
  return (
    <div
      className={cn("text-[#0F1A3D] dark:text-foreground", className)}
      dangerouslySetInnerHTML={{ __html: drawn("whole", own, "DeepLit") }}
    />
  );
}

/** The icon beside the wordmark, "Deep Literature" under the wordmark. `size` (any CSS length)
 * is the icon's height and sets the rest; it is drawn for a light ground in either theme. */
export function BrandLockup({ size, className }: { size: string; className?: string }) {
  const own = useOwn();
  return (
    <div className={cn("flex items-center text-[#0F1A3D]", className)} style={{ height: size, gap: `calc(${size} * 0.14)` }}>
      <div className="h-full shrink-0" dangerouslySetInnerHTML={{ __html: drawn("icon", `${own}i`) }} />
      <div className="flex flex-col" style={{ paddingTop: `calc(${size} * 0.08)` }}>
        <div style={{ height: `calc(${size} * 0.72)` }} dangerouslySetInnerHTML={{ __html: drawn("wordmark", `${own}w`, "DeepLit") }} />
        <span
          className="tracking-[0.2em] whitespace-nowrap text-[#1b2450]"
          style={{ fontSize: `calc(${size} * 0.19)`, paddingLeft: `calc(${size} * 0.03)` }}
        >
          Deep Literature
        </span>
      </div>
    </div>
  );
}

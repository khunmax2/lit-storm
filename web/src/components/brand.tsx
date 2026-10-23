// DeepLit's mark: the icon (the sidebar, the favicon) and the full logo, the icon over the
// wordmark (the sign-in pages). Drawn by the owner, 2026-10-23.
import iconUrl from "@/assets/deeplit-icon.svg";
import logoRaw from "@/assets/deeplit-logo.svg?raw";
import { cn } from "@/lib/utils";

// "Deep" is drawn in near-black (#0F1A3D), which a dark theme would swallow: it takes the text
// colour instead, that same near-black on a light theme. The SVG's fixed size gives way to its box.
const LOGO = logoRaw
  .replace('fill="#0F1A3D"', 'fill="currentColor"')
  .replace(/ width="\d+" height="\d+"/, ' class="h-full w-auto" role="img" aria-label="DeepLit"');

export function BrandIcon({ className }: { className?: string }) {
  return <img src={iconUrl} alt="" className={cn("shrink-0", className)} />;
}

export function BrandLogo({ className }: { className?: string }) {
  return (
    <div
      className={cn("text-[#0F1A3D] dark:text-foreground", className)}
      dangerouslySetInnerHTML={{ __html: LOGO }}
    />
  );
}

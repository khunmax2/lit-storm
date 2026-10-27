// DeepLit: the report renders inside a shadow root, so lookups by id and the colour tokens are read from it rather
// than from the document. MraView sets these when it mounts.
export const host: { root: Document | ShadowRoot; el: Element | null } = {
  root: typeof document !== "undefined" ? document : (null as unknown as Document),
  el: null,
};

/** DeepLit's sidebar beside the report from `md` up (16rem): MRA's layout widths (its Tailwind breakpoints from `md`,
 * report.css, and the media queries below) are moved up by it, so a column switch happens at the width MRA meant. */
export const APP_CHROME_PX = 256;

export function byId(id: string): HTMLElement | null {
  return host.root.getElementById(id) as HTMLElement | null;
}

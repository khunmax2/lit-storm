// DeepLit: the report renders inside a shadow root, so lookups by id and the colour tokens are read from it rather
// than from the document. MraView sets these when it mounts.
export const host: { root: Document | ShadowRoot; el: Element | null } = {
  root: typeof document !== "undefined" ? document : (null as unknown as Document),
  el: null,
};

export function byId(id: string): HTMLElement | null {
  return host.root.getElementById(id) as HTMLElement | null;
}

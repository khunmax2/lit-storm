// Markdown a model wrote, as HTML for the page: raw HTML stays text (markdown-it
// with html off, which also refuses javascript: links), and each [n] becomes a
// small link to the source it cites, or goes when nothing answers to it.
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: false, linkify: false });

const escape = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

export type Cite = { url: string; title: string } | undefined;

export function modelHtml(text: string, cite: (n: number) => Cite) {
  return md.render(text || "").replace(/\s?\[(\d+)\]/g, (_, n) => {
    const s = cite(Number(n));
    if (!s || !/^https?:\/\//.test(s.url)) return "";
    return `<a class="iv-cite" href="${escape(s.url)}" target="_blank" rel="noreferrer" title="${escape(s.title || s.url)}">${n}</a>`;
  });
}

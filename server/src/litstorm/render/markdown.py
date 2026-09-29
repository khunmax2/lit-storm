"""report.json as Markdown: the text, then the numbered sources."""

from litstorm.render.html import LABELS


def _sections(sections, level, out):
    for s in sections:
        out.append(f"{'#' * min(level, 6)} {s['heading']}")
        if s["body"]:
            out.append(s["body"])
        _sections(s["children"], level + 1, out)


def render(report, with_evidence=False):
    labels = LABELS[report["language"]]
    out = [f"# {report['title']}"]
    if report["lead"]:
        out.append(report["lead"])
    _sections(report["sections"], 2, out)

    out.append(f"## {labels['sources']}")
    for s in report["sources"]:
        entry = [f"{s['id']}. [{s['title']}]({s['url']})"]
        if with_evidence:
            if s["evidence"]:
                entry.append(f"   *{labels['excerpt_note']}*")
                entry.extend(f"   > {e.strip()}" for e in s["evidence"])
            else:
                entry.append(f"   *{labels['no_evidence']}*")
        out.append("\n".join(entry))
    return "\n\n".join(out) + "\n"

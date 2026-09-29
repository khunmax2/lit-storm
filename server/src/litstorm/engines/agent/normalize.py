"""Agent Research's markdown report -> report.json (litstorm.report).

The writer agents end the report with a reference list, "[n] url" per line,
under "References:" (or a heading of that name), and cite "[n]" inline. The
deep level's long writer adds a title ("# ...") and a table of contents.

Here: the title comes from the "# " heading when there is one; text before
the first "## " is the lead; "## " headings are sections and "### " their
children. Citations are renumbered in reading order; a marker whose number
has no reference is dropped, as is a reference nothing cites. Titles and
descriptions come from what the searches returned for each URL. No Evidence:
the agents summarise pages rather than keep passages (docs/web-app-design.md,
รุ่นสอง: Agent Research).
"""

import re
from urllib.parse import urlparse

from litstorm.report import SCHEMA

REFERENCES = re.compile(
    # "References:", "## Sources", "**รายการอ้างอิง:**" (seen writing in Thai)
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(references?|sources?|(?:รายการ|แหล่ง|เอกสาร)?อ้างอิง)\s*:?\s*(?:\*\*)?\s*:?\s*$",
    re.IGNORECASE,
)
REFERENCE_LINE = re.compile(r"^\s*(?:[-*]\s*)?\[?(\d+)\]?[.:)]?\s+(.*)$")
URL = re.compile(r"https?://[^\s)\]>]+")
GROUPED = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)+)\]")
MARKER = re.compile(r"\[(\d+)\]")
TOC = re.compile(r"^(table of contents|contents|สารบัญ)$", re.IGNORECASE)


def split_references(markdown):
    """(body, {n: url}) — the reference list taken off the end."""
    lines = markdown.splitlines()
    start = None
    for i in range(len(lines) - 1, -1, -1):
        if REFERENCES.match(lines[i]):
            start = i
            break
    if start is None:
        return markdown, {}
    refs = {}
    for line in lines[start + 1:]:
        m = REFERENCE_LINE.match(line)
        url = URL.search(line)
        if m and url:
            refs[int(m.group(1))] = url.group(0).rstrip(".,;")
    return "\n".join(lines[:start]).rstrip(), refs


def _sections(body):
    """(title, lead, sections) from markdown headings."""
    title, lead, sections = None, [], []
    section = child = None  # where body lines go: the child if any, else the section
    for line in body.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not heading:
            (child or section or {"body": lead})["body"].append(line)
            continue
        level, text = len(heading.group(1)), heading.group(2).strip()
        if level == 1 and title is None and not sections:
            title = text
        elif level <= 2 or section is None:
            section, child = {"heading": text, "body": [], "children": []}, None
            sections.append(section)
        else:
            child = {"heading": text, "body": [], "children": []}
            section["children"].append(child)
    # Tables of contents repeat the headings; the reader has its own.
    sections = [s for s in sections if not TOC.match(s["heading"])]
    return title, "\n".join(lead).strip(), sections


def normalize(markdown, topic, language, found):
    """report.json from the agent's markdown. `found` maps a URL to what the
    search returned for it: {"title", "description"}."""
    body, refs = split_references(markdown or "")
    body = GROUPED.sub(lambda m: "".join(f"[{n.strip()}]" for n in re.split(r"[,;]", m.group(1))), body)
    title, lead, raw_sections = _sections(body)

    renumber, sources = {}, []

    def cite(match):
        n = int(match.group(1))
        url = refs.get(n)
        if not url:
            return ""
        if url not in renumber:
            renumber[url] = len(renumber) + 1
            seen = found.get(url) or {}
            sources.append({
                "id": renumber[url],
                "url": url,
                "title": (seen.get("title") or "").strip() or urlparse(url).netloc or url,
                "description": (seen.get("description") or "").strip(),
                "evidence": [],
            })
        return f"[{renumber[url]}]"

    def text(lines):
        joined = MARKER.sub(cite, "\n".join(lines) if isinstance(lines, list) else lines)
        # A dropped marker leaves its space behind: "in [5]." -> "in ."
        joined = re.sub(r"[ \t]+(?=[.,;:!?])", "", joined)
        # A rule the writer drew above its reference list ends a section.
        return re.sub(r"(?:\n\s*(?:-{3,}|\*{3,}|_{3,})\s*)+$", "", joined.rstrip()).strip()

    counter = [0]

    def section(raw):
        counter[0] += 1
        out = {"id": f"s{counter[0]}", "heading": raw["heading"], "body": text(raw["body"]), "children": []}
        out["children"] = [section(c) for c in raw["children"]]
        return out

    lead_text = text(lead)
    sections = [section(s) for s in raw_sections]
    return {
        "schema": SCHEMA,
        "engine": "agent",
        "title": title or topic,
        "language": language,
        "lead": lead_text,
        "sections": sections,
        "sources": sources,
    }

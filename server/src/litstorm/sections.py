"""The sections an owner wants a report to have (docs/web-app-design.md,
รุ่นสอง: โครงร่างที่ผู้ใช้กำหนดและ Project).

One heading per line in the composer. They are the report's top-level
sections, in that order and under those names; what goes under each is the
Engine's to plan. Used by STORM, whose outline they replace at the top, and
by Agent Research at its deep level, whose report plan they replace.
"""

import re

MAX_SECTIONS = 10
MAX_LENGTH = 120

# What people type in front of a heading: "#", "-", "*", "•", "1.", "1)".
_MARKER = re.compile(r"^\s*(?:#+|[-*•]|\d+[.)])\s*")


def clean(lines):
    """The headings as they will be used: markers, blanks and repeats gone."""
    out = []
    for line in lines or []:
        heading = _MARKER.sub("", line or "").strip()[:MAX_LENGTH]
        if heading and heading.casefold() not in {h.casefold() for h in out}:
            out.append(heading)
    return out[:MAX_SECTIONS]


def _loose(text):
    return re.sub(r"[\s_:]+", " ", re.sub(r"\(.*?\)", "", text or "")).strip().casefold()


def match(wanted, names):
    """For each wanted heading, the index in `names` of the section the
    Engine planned for it, or None; each planned section used once. An
    exact match (ignoring case and brackets) wins over one name containing
    the other."""
    loose = [_loose(n) for n in names]
    used = set()
    found = []
    for heading in wanted:
        h = _loose(heading)
        index = next((i for i, n in enumerate(loose) if i not in used and n == h), None)
        if index is None and h:
            index = next((i for i, n in enumerate(loose) if i not in used and n and (h in n or n in h)), None)
        if index is not None:
            used.add(index)
        found.append(index)
    return found


def draft(wanted):
    """The wanted headings as an outline for a model to fill in."""
    return "\n".join(f"# {h}" for h in wanted)

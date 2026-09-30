"""A Project's instructions, as the Engines use them (docs/CONTEXT.md,
Project instructions; docs/web-app-design.md, รุ่นสอง: โครงร่างที่ผู้ใช้
กำหนดและ Project).

Two texts the owner writes for a Project:

- search scope — what to look for and where. It steers the stages that ask
  and search, beside the answers to the clarifying questions;
- writing style — how the report is written. It goes to the stages that
  write.

A Run started in the Project keeps a copy, so changing the instructions, or
moving the topic out, does not change a Run already made. Research started
outside any Project has none.
"""

from litstorm import refine

MAX_LENGTH = 2000


def snapshot(project):
    """What a new Run keeps of its Project's instructions."""
    if project is None:
        return {}
    kept = {
        "search_scope": (project.search_scope or "").strip()[:MAX_LENGTH],
        "writing_style": (project.writing_style or "").strip()[:MAX_LENGTH],
    }
    return {k: v for k, v in kept.items() if v}


def focus(config):
    """What steers research: the clarifying answers, then the search scope."""
    parts = [refine.focus(config.refinement), (config.instructions or {}).get("search_scope", "")]
    return "; ".join(p for p in parts if p)


def style(config):
    return (config.instructions or {}).get("writing_style", "")

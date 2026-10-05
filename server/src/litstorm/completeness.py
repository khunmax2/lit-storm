"""Whether a written report is whole, or the model stopped part-way.

A model can stop writing mid-report: cut off at its token limit, filtered,
or ending its turn early. Seen 2026-10-06 on Agent Research: 752 characters
ending on a bare heading ("### CATL"), from 14 pages read. The Run then
failed as if the research had found nothing (outcomes.EMPTY_REPORT), and
nothing tried again though everything needed to write was at hand.

`check` reads the signs; an Engine that can write again calls it on its
draft, writes once more if it fails, and gives up as
outcomes.TRUNCATED_REPORT, which tells the owner what happened and gives the
quota back (docs/web-app-design.md, ความล้มเหลวกับการคืนโควตา).

The signs are conservative: a false alarm costs one more writing call, a
missed one a report that stops mid-sentence. Thai is not held to Latin
punctuation: a Thai sentence ends without a mark.
"""

import re
from dataclasses import dataclass, field

# Why a model stopped that means it did not finish (OpenAI-style APIs).
CUT_OFF = {"length", "content_filter"}
# A report shorter than this, from at least SOME_SOURCES pages, is a stub.
SHORT = 1200
SOME_SOURCES = 3

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
# How a whole paragraph may end: a mark, a citation, a closing bracket or
# quote, or a table row's bar.
_ENDS_WELL = re.compile(r"""[.!?。…:;)\]"'”’»|*_`ๆฯ]\s*$""")
_LATIN_END = re.compile(r"[A-Za-z0-9,\-–]\s*$")
# A line that is an item, not prose: a reference ("[3] https://…"), a list
# entry, or anything carrying an address. How a report's list ends.
_ITEM = re.compile(r"^\s*(\[\d+\]|[-*+]\s|\d+[.)]\s)|https?://")


@dataclass
class Verdict:
    reasons: list = field(default_factory=list)

    @property
    def whole(self):
        return not self.reasons


def check(markdown, *, sources_read=0, finish_reasons=()):
    """What looks unfinished about a report, if anything."""
    verdict = Verdict()
    stopped = sorted({r for r in finish_reasons if r in CUT_OFF})
    if stopped:
        verdict.reasons.append(f"stopped: {', '.join(stopped)}")
    text = (markdown or "").strip()
    if not text:
        verdict.reasons.append("empty")
        return verdict
    lines = [line for line in text.splitlines() if line.strip()]
    last = lines[-1]
    if _HEADING.match(last):
        verdict.reasons.append("ends on a heading")
    elif not _ITEM.search(last) and not _ENDS_WELL.search(last) and _LATIN_END.search(last):
        # Latin text ending on a letter, digit or comma: a sentence cut
        # off. Thai, which ends without a mark, is left alone.
        verdict.reasons.append("ends mid-sentence")
    if sources_read >= SOME_SOURCES and len(text) < SHORT:
        verdict.reasons.append(f"{len(text)} characters from {sources_read} sources")
    return verdict


def summary(verdict):
    return "; ".join(verdict.reasons)

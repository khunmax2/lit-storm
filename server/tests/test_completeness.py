"""A report the model stopped writing part-way is seen, written again once,
and failed as such if it stops again (litstorm.completeness)."""

import asyncio

import pytest

from litstorm import completeness, outcomes
from litstorm.engines.base import EngineFailure

CUT = (
    "## The Evolution and Commercial Landscape of Sodium-Ion Battery Technology\n\n"
    "As of October 2026, sodium-ion battery technology has moved into large-scale deployment.\n\n"
    "## Key Industry Players and Commercial Milestones\n\n"
    "The market is led by a mix of specialized developers and large manufacturers.\n\n"
    "### CATL"
)  # what came back on 2026-10-06, shortened
WHOLE = "## Heat pumps\n\n" + "A heat pump moves heat rather than making it [1]. " * 40 + "\n\nReferences:\n[1] https://example.org/a/123"


@pytest.mark.parametrize(
    "text, sources, reasons",
    [
        (CUT, 14, ["ends on a heading", f"{len(CUT)} characters from 14 sources"]),
        ("A paragraph that stops in the middle of", 0, ["ends mid-sentence"]),
        ("", 0, ["empty"]),
        (WHOLE, 14, []),
        ("Body [1].\n\nอ้างอิง:\n[13] https://www.nationthailand.com/news/policy/40058494", 0, []),
        ("ย่อหน้าภาษาไทยจบโดยไม่มีจุด", 0, []),  # Thai ends without a mark
        ("| a | b |\n|---|---|\n| 1 | 2 |", 0, []),
        ("- one item\n- two items", 0, []),
        ("Short, but whole.", 2, []),  # few pages read: short is fine
    ],
)
def test_the_signs_of_a_report_left_unfinished(text, sources, reasons):
    assert completeness.check(text, sources_read=sources).reasons == reasons


def test_a_model_that_says_it_was_cut_off_is_believed():
    verdict = completeness.check(WHOLE, finish_reasons=["stop", "length"])
    assert verdict.reasons == ["stopped: length"] and not verdict.whole
    assert completeness.check(WHOLE, finish_reasons=["stop"]).whole


class Progress:
    def __init__(self):
        self.notes = []

    def note(self, kind, **data):
        self.notes.append((kind, data))


def _writer(*drafts, finish=None):
    """A writer that answers with each draft in turn, saying why it stopped."""
    from litstorm.engines.agent.engine import FINISHES

    calls = []

    async def write(*args, **kwargs):
        calls.append((args, kwargs))
        if finish and FINISHES.get() is not None:
            FINISHES.get().append(finish[len(calls) - 1])
        return drafts[len(calls) - 1]

    return write, calls


def _run(write, tmp_path, progress):
    from litstorm.engines.agent.engine import written_whole

    found = {f"https://p{i}.test": {} for i in range(14)}
    return asyncio.run(written_whole(write, ("topic",), {"length": ""}, progress=progress, workspace=str(tmp_path), found=found))


def test_a_whole_report_is_written_once(tmp_path):
    write, calls = _writer(WHOLE)
    progress = Progress()
    assert _run(write, tmp_path, progress) == WHOLE
    assert len(calls) == 1 and [k for k, _ in progress.notes] == ["writer"]


def test_an_unfinished_report_is_written_again_with_the_same_findings(tmp_path):
    write, calls = _writer(CUT, WHOLE)
    progress = Progress()
    assert _run(write, tmp_path, progress) == WHOLE
    assert calls == [(("topic",), {"length": ""})] * 2  # the same call: nothing searched again
    assert [k for k, _ in progress.notes] == ["writer", "rewritten", "writer"]
    assert (tmp_path / "report-unfinished-1.md").read_text(encoding="utf-8") == CUT


def test_a_cut_off_the_model_admits_to_is_written_again(tmp_path):
    write, calls = _writer(WHOLE, WHOLE, finish=["length", "stop"])
    progress = Progress()
    assert _run(write, tmp_path, progress) == WHOLE
    assert len(calls) == 2
    assert progress.notes[0][1]["finish_reasons"] == ["length"]


def test_unfinished_twice_fails_as_truncated_and_gives_the_quota_back(tmp_path):
    write, calls = _writer(CUT, CUT)
    with pytest.raises(EngineFailure) as failed:
        _run(write, tmp_path, Progress())
    assert failed.value.reason == outcomes.TRUNCATED_REPORT and "twice" in str(failed.value)
    assert outcomes.refunds_quota(outcomes.TRUNCATED_REPORT)
    assert (tmp_path / "report-unfinished-2.md").exists()

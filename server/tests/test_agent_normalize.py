"""Agent Research's markdown turned into report.json."""

from litstorm import report as report_mod
from litstorm.engines.agent import normalize

ITERATIVE = """Songkran is the Thai New Year [1]. It falls in April [2, 3].

## History
It began as a rite of passage [2]. Water marks renewal [4].

### In Chiang Mai
The festival lasts longer in the north [3].

## Today
Tourists join in [5].

References:
[1] https://a.test/one
[2] https://b.test/two
[3] https://c.test/three
[4] https://d.test/four
"""

DEEP = """# Songkran: A Report

## Table of Contents

1. Origins
2. Customs

## Origins
Brahmin roots [1].

## Customs
Water blessing [2].

## References:

[1] https://a.test/one
[2] https://b.test/two"""


def test_the_iterative_report_becomes_sections_with_numbered_sources():
    found = {"https://a.test/one": {"title": "One", "description": "first"}}
    report = normalize.normalize(ITERATIVE, "Songkran", "en", found)
    report_mod.validate(report)
    assert report["title"] == "Songkran"
    assert report["lead"] == "Songkran is the Thai New Year [1]. It falls in April [2][3]."
    history, today = report["sections"]
    assert history["heading"] == "History" and history["children"][0]["heading"] == "In Chiang Mai"
    assert history["children"][0]["body"] == "The festival lasts longer in the north [3]."
    assert history["body"] == "It began as a rite of passage [2]. Water marks renewal [4]."
    assert today["body"] == "Tourists join in."  # [5] has no reference: dropped
    assert [s["url"] for s in report["sources"]] == [
        "https://a.test/one", "https://b.test/two", "https://c.test/three", "https://d.test/four"
    ]
    assert report["sources"][0]["title"] == "One" and report["sources"][1]["title"] == "b.test"
    assert all(s["evidence"] == [] for s in report["sources"])


def test_the_deep_report_keeps_its_title_and_drops_the_contents():
    report = normalize.normalize(DEEP, "Songkran", "th", {})
    report_mod.validate(report)
    assert report["title"] == "Songkran: A Report"
    assert [s["heading"] for s in report["sections"]] == ["Origins", "Customs"]
    assert [s["id"] for s in report["sources"]] == [1, 2]


def test_a_thai_reference_list_is_found():
    """As a real Run wrote it, after a rule."""
    md = "## ผลกระทบ\nข้อความ [1, 2]\n\n---\n**รายการอ้างอิง:**\n[1] https://a.test/x\n[2] https://b.test/y"
    report = normalize.normalize(md, "t", "th", {})
    report_mod.validate(report)
    assert report["sections"][0]["body"] == "ข้อความ [1][2]"
    assert len(report["sources"]) == 2


def test_uncited_references_are_left_out_and_citations_follow_reading_order():
    md = "B first [2], then A [1].\n\nReferences:\n[1] https://a.test\n[2] https://b.test\n[3] https://c.test"
    report = normalize.normalize(md, "t", "en", {})
    report_mod.validate(report)
    assert report["lead"] == "B first [1], then A [2]."
    assert [s["url"] for s in report["sources"]] == ["https://b.test", "https://a.test"]

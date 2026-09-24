"""STORM's files on disk, turned into report.json."""

import json

import pytest

from litstorm import report
from litstorm.engines.storm.normalize import POLISHED_REFERENCES, normalize, parse_sections

ARTICLE = """# summary

สงกรานต์เป็นเทศกาลปีใหม่ไทย [4][1].

# ประวัติ

เริ่มจากคติพราหมณ์ [4].

## ที่มาของชื่อ

มาจากภาษาสันสกฤต [9] และ [7].

# ประเพณี

รดน้ำดำหัว [1].
"""


def refs(**index):
    return {
        "url_to_unified_index": {f"https://s/{n}": n for n in index.values()},
        "url_to_info": {
            f"https://s/{n}": {
                "url": f"https://s/{n}",
                "title": f"Source {n}",
                "description": "",
                "snippets": [f"passage {n}", "  "],
                "meta": {},
                "citation_uuid": -1,
            }
            for n in index.values()
        },
    }


@pytest.fixture
def article_dir(tmp_path):
    (tmp_path / "storm_gen_article_polished.txt").write_text(ARTICLE, encoding="utf-8")
    # 7 is cited in the text but has no source; 2 has a source but is not cited.
    (tmp_path / POLISHED_REFERENCES).write_text(
        json.dumps(refs(a=1, b=2, c=4, d=9)), encoding="utf-8"
    )
    return tmp_path


def test_lead_and_nested_sections():
    lead, sections = parse_sections(ARTICLE)
    assert lead.startswith("สงกรานต์")
    assert [s["heading"] for s in sections] == ["ประวัติ", "ประเพณี"]
    assert sections[0]["children"][0]["heading"] == "ที่มาของชื่อ"
    assert [s["id"] for s in report.walk(sections)] == ["s1", "s2", "s3"]


def test_sources_renumbered_in_reading_order(article_dir):
    result, dropped = normalize(str(article_dir), "สงกรานต์", "th")

    assert result["lead"] == "สงกรานต์เป็นเทศกาลปีใหม่ไทย [1][2]."
    assert [(s["id"], s["url"]) for s in result["sources"]] == [
        (1, "https://s/4"),
        (2, "https://s/1"),
        (3, "https://s/9"),
    ]
    child = result["sections"][0]["children"][0]
    assert child["body"] == "มาจากภาษาสันสกฤต [3] และ."
    assert dropped == 1


def test_uncited_sources_are_left_out_and_blank_evidence_dropped(article_dir):
    result, _ = normalize(str(article_dir), "สงกรานต์", "th")
    assert "https://s/2" not in {s["url"] for s in result["sources"]}
    assert result["sources"][0]["evidence"] == ["passage 4"]


def test_draft_used_when_polishing_did_not_finish(tmp_path):
    (tmp_path / "storm_gen_article.txt").write_text("# A\n\nText [1].", encoding="utf-8")
    (tmp_path / "url_to_info.json").write_text(json.dumps(refs(a=1)), encoding="utf-8")
    result, _ = normalize(str(tmp_path), "t", "en")
    assert result["lead"] == ""
    assert result["sections"][0]["body"] == "Text [1]."


def test_polished_text_is_never_read_with_the_drafts_references(tmp_path):
    # STORM renumbers citations when polishing but leaves url_to_info.json
    # with the draft's numbers. Without our saved references, the polished
    # text cannot be trusted; the draft is read instead.
    (tmp_path / "storm_gen_article_polished.txt").write_text("# A\n\nPolished [2].", encoding="utf-8")
    (tmp_path / "storm_gen_article.txt").write_text("# A\n\nDraft [1].", encoding="utf-8")
    (tmp_path / "url_to_info.json").write_text(json.dumps(refs(a=1)), encoding="utf-8")
    result, _ = normalize(str(tmp_path), "t", "en")
    assert result["sections"][0]["body"] == "Draft [1]."


@pytest.mark.slow
def test_storm_polishing_renumbers_citations_and_the_object_knows_it():
    """Reproduce the STORM behaviour the engine works around."""
    from knowledge_storm.interface import Information
    from knowledge_storm.storm_wiki.modules.storm_dataclass import StormArticle

    def info(n):
        return Information(url=f"https://s/{n}", description="", snippets=[f"p{n}"], title=f"S{n}")

    draft = StormArticle("t")
    draft.update_section("# One\nFirst [1].", [info(1)])
    draft.update_section("# Two\nSecond [1].", [info(2)])
    draft.post_processing()
    draft_index = dict(draft.reference["url_to_unified_index"])
    assert draft_index == {"https://s/1": 1, "https://s/2": 2}

    # What polish_article does: a lead citing source 2 first, then reorder.
    import copy
    from knowledge_storm.utils import ArticleTextProcessing

    polished = copy.deepcopy(draft)
    text = "# summary\nLead [2].\n\n" + draft.to_string()
    polished.insert_or_create_section(ArticleTextProcessing.parse_article_into_dict(text))
    polished.post_processing()

    assert polished.reference["url_to_unified_index"] == {"https://s/2": 1, "https://s/1": 2}
    assert polished.reference["url_to_unified_index"] != draft_index  # the file would be stale


def test_back_matter_is_dropped_in_thai_and_english(tmp_path):
    text = (
        "# สถาปัตยกรรม\n\nเนื้อหา [1].\n\n"
        "# ดูเพิ่ม (See Also)\n\n* โมเดลภาษา [2]\n\n"
        "# การอ้างอิง (References)\n\nงานวิจัย [2]\n\n"
        "# See also\n\n* x\n"
    )
    (tmp_path / "storm_gen_article.txt").write_text(text, encoding="utf-8")
    (tmp_path / "url_to_info.json").write_text(json.dumps(refs(a=1, b=2)), encoding="utf-8")
    result, _ = normalize(str(tmp_path), "t", "th")

    assert [s["heading"] for s in result["sections"]] == ["สถาปัตยกรรม"]
    # Source 2 was cited only from the back matter, so it goes too.
    assert [s["url"] for s in result["sources"]] == ["https://s/1"]


def test_validate_rejects_a_dangling_citation():
    bad = {
        "schema": 1, "engine": "x", "title": "t", "language": "en",
        "lead": "[2]", "sections": [], "sources": [],
    }
    with pytest.raises(report.ReportError, match="no source"):
        report.validate(bad)


def test_empty_report_is_empty():
    empty = {
        "schema": 1, "engine": "x", "title": "t", "language": "en",
        "lead": "  ", "sections": [], "sources": [],
    }
    assert report.is_empty(empty)

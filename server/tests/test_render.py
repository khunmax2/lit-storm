"""HTML and Markdown exports drawn from report.json."""

import os
import re

import pytest

from litstorm.render import html, markdown

REPORT = {
    "schema": 1,
    "engine": "storm",
    "title": "สงกรานต์",
    "language": "th",
    "lead": "เทศกาลปีใหม่ไทย [1]. <script>alert(1)</script>",
    "sections": [
        {
            "id": "s1",
            "heading": "ประวัติ",
            "body": "เริ่มจากคติพราหมณ์ [2] และ [javascript](javascript:alert(1)).",
            "children": [
                {"id": "s2", "heading": "ชื่อ", "body": "สันสกฤต [1].", "children": []}
            ],
        }
    ],
    "sources": [
        {"id": 1, "url": "https://a.example/x", "title": "A", "description": "", "evidence": ["ข้อความ 1"]},
        {"id": 2, "url": "javascript:alert(2)", "title": "B", "description": "", "evidence": []},
    ],
}


def test_citations_link_to_their_source():
    page = html.render(REPORT)
    # A pill showing the number; its brackets stay in the text for copying.
    assert '<a class="cite" href="#src-1"><span class="b">[</span>1<span class="b">]</span></a>' in page
    assert 'id="src-2"' in page


def test_contents_list_every_section():
    page = html.render(REPORT)
    assert '<a href="#s1">ประวัติ</a>' in page and '<a href="#s2">ชื่อ</a>' in page
    assert '<h3 id="s2">' in page


def test_model_output_cannot_run_script():
    page = html.render(REPORT, with_evidence=True)
    assert "<script>" not in page
    assert 'href="javascript:' not in page


def test_evidence_only_when_asked_and_marked_as_excerpt():
    assert "ข้อความ 1" not in html.render(REPORT)
    page = html.render(REPORT, with_evidence=True)
    assert "ข้อความ 1" in page
    assert "ไม่ใช่ต้นฉบับเต็ม" in page
    assert "ระบบไม่ได้บันทึกข้อความหลักฐาน" in page  # source 2 has none


def test_page_needs_no_network():
    page = html.render(REPORT, with_evidence=True)
    assert not re.search(r'<(script|link|img)\b', page)
    assert "@import" not in page


def test_markdown_export():
    text = markdown.render(REPORT, with_evidence=True)
    assert text.startswith("# สงกรานต์")
    assert "### ชื่อ" in text
    assert "1. [A](https://a.example/x)" in text
    assert "   > ข้อความ 1" in text


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") and not os.environ.get("LITSTORM_PDF_TEST"),
    reason="needs a Chromium: set LITSTORM_PDF_BROWSER_CHANNEL=msedge or LITSTORM_PDF_TEST=1",
)
def test_pdf_prints(tmp_path):
    from litstorm.render import pdf

    out = pdf.render(REPORT, str(tmp_path / "r.pdf"), with_evidence=True)
    with open(out, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_printing_opens_the_evidence():
    # Chromium does not print what a closed <details> holds.
    assert "<details open>" in html.render(REPORT, with_evidence=True, expanded=True)
    assert "<details open>" not in html.render(REPORT, with_evidence=True)


def test_fonts_travel_inside_the_page():
    # The web app's faces, so a Thai report looks the same without Thai fonts
    # installed; data: URLs, not the network.
    page = html.render(REPORT)
    assert page.count("@font-face") == 5
    assert "url(data:font/woff2;base64," in page
    assert not re.search(r"url\((?!data:)", page)


def test_facts_above_the_title():
    from datetime import datetime, timezone

    page = html.render(REPORT, engine_label="STORM", finished_at=datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc))
    assert '<span class="mode">STORM</span>' in page
    # Bangkok time and the Buddhist year: 30 Sep 2026 03:00 there.
    assert "30 ก.ย. 2569" in page
    assert "อ่านราว 1 นาที" in page


def test_sections_are_numbered():
    page = html.render(REPORT)
    assert '<h2 id="s1"><span class="n">01</span>' in page
    assert '<h3 id="s2"><span class="n">1.1</span>' in page

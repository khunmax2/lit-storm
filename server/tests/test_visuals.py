"""Visual blocks: facts cut from the evidence, and nothing kept that the
facts do not bear out (litstorm.visuals)."""

import copy

from litstorm import visuals

REPORT = {
    "schema": 1,
    "engine": "storm",
    "title": "ทุเรียน",
    "language": "th",
    "lead": "ทุเรียนเป็นผลไม้ส่งออก [1]",
    "sections": [
        {"id": "s1", "heading": "ตลาด", "body": "ส่งออกไปจีนมาก [1] [2]", "children": [
            {"id": "s2", "heading": "ราคา", "body": "ราคาสูงขึ้น [3]", "children": []},
        ]},
    ],
    "sources": [
        {"id": 1, "url": "https://a.example", "title": "A", "description": "",
         "evidence": ["ในปี 2566 ไทยส่งออกทุเรียนสด 929,000 ตัน มูลค่ากว่า 110,000 ล้านบาท"]},
        {"id": 2, "url": "https://b.example", "title": "B", "description": "",
         "evidence": ["ปี ๒๕๖๕ ส่งออก ๘๒๕,๐๐๐ ตัน ระบบ GAP คือมาตรฐานการปฏิบัติทางการเกษตรที่ดีสำหรับฟาร์ม"]},
        {"id": 3, "url": "https://c.example", "title": "C", "description": "",
         "evidence": ["Monthong accounts for 42.5% of plantings. PMCS is a traceability model used by exporters since 2019."]},
    ],
}


def _fact(facts, words):
    return next(f["id"] for f in facts if words in f["text"])


def test_facts_are_numbered_and_keep_their_source():
    facts = visuals.facts(REPORT)
    assert [f["id"] for f in facts] == [f"F{i}" for i in range(1, len(facts) + 1)]
    assert all(f["origin"] == "evidence" for f in facts)
    by_source = {f["source"] for f in facts}
    assert by_source == {1, 2, 3}


def test_numbers_are_read_in_thai_digits_and_with_thousands_marks():
    assert 825000.0 in visuals.numbers_in("ส่งออก ๘๒๕,๐๐๐ ตัน")
    assert 42.5 in visuals.numbers_in("42.5%")
    assert 42.5 in visuals.numbers_in("42,5 %")


def test_a_figure_is_kept_only_when_its_fact_holds_it():
    facts = visuals.facts(REPORT)
    f1, f2 = _fact(facts, "929,000"), _fact(facts, "๘๒๕")
    blocks, dropped = visuals.check([{
        "type": "stat_cards", "anchor": {"section": "s1"}, "title": "ตัวเลขสำคัญ",
        "items": [
            {"label": "ส่งออก 2566", "value": 929000, "unit": "ตัน", "fact": f1},
            {"label": "ส่งออก 2565", "value": "825,000", "unit": "ตัน", "fact": f2},
            {"label": "แต่งเอง", "value": 999, "unit": "ตัน", "fact": f1},
            {"label": "ไม่มีที่มา", "value": 929000, "unit": "ตัน", "fact": "F999"},
        ],
    }], REPORT, facts)
    assert not dropped
    [block] = blocks
    assert [i["value"] for i in block["items"]] == [929000, 825000]
    # The source is the fact's, whatever the model said.
    assert block["items"][1]["cite"]["source"] == 2
    assert block["sources"] == [1, 2] and block["anchor"] == "s1"


def test_a_chart_left_too_thin_is_dropped_whole():
    facts = visuals.facts(REPORT)
    f1 = _fact(facts, "929,000")
    thin = {"type": "chart", "chart": "bar", "series": [{"name": "x", "points": [
        {"x": "2566", "y": 929000, "fact": f1},
        {"x": "2567", "y": 1000000, "fact": f1},
        {"x": "2568", "y": 1100000, "fact": f1},
    ]}]}
    blocks, dropped = visuals.check([thin], REPORT, facts)
    assert not blocks and dropped[0]["type"] == "chart"


def test_chart_kinds_that_would_mislead_become_bars():
    facts = visuals.facts(REPORT)
    f1, f2 = _fact(facts, "929,000"), _fact(facts, "๘๒๕")
    points = [{"x": "ทุเรียนสด", "y": 929000, "fact": f1}, {"x": "ปีก่อน", "y": 825000, "fact": f2}]
    line = {"type": "chart", "chart": "line", "series": [{"name": "ส่งออก", "points": points}]}
    pie = {"type": "chart", "chart": "pie", "series": [{"name": "a", "points": points}, {"name": "b", "points": points}]}
    blocks, _ = visuals.check([line, pie], REPORT, facts)
    assert [b["chart"] for b in blocks] == ["bar", "bar"]


def test_a_line_over_years_is_ordered():
    facts = visuals.facts(REPORT)
    f1, f2 = _fact(facts, "929,000"), _fact(facts, "๘๒๕")
    line = {"type": "chart", "chart": "line", "unit": "ตัน", "series": [{"name": "ส่งออก", "points": [
        {"x": "2566", "y": 929000, "fact": f1}, {"x": "2565", "y": 825000, "fact": f2}]}]}
    [block], _ = visuals.check([line], REPORT, facts)
    assert block["chart"] == "line"
    assert [p["x"] for p in block["series"][0]["points"]] == ["2565", "2566"]


def test_timeline_years_match_in_either_era_and_sort():
    facts = visuals.facts(REPORT)
    f1, f3 = _fact(facts, "929,000"), _fact(facts, "PMCS")
    blocks, _ = visuals.check([{"type": "timeline", "events": [
        {"date": "2566", "label": "ส่งออกเกือบล้านตัน", "fact": f1},
        {"date": "2019", "label": "เริ่มใช้ PMCS", "fact": f3},
        {"date": "2001", "label": "ไม่มีในข้อเท็จจริง", "fact": f3},
    ]}], REPORT, facts)
    [block] = blocks
    assert [e["date"] for e in block["events"]] == ["2019", "2566"]


def test_a_glossary_term_must_be_what_its_fact_talks_about():
    facts = visuals.facts(REPORT)
    f2, f3 = _fact(facts, "GAP"), _fact(facts, "PMCS")
    blocks, _ = visuals.check([{"type": "glossary", "terms": [
        {"term": "GAP", "definition": "มาตรฐานการปฏิบัติทางการเกษตรที่ดี", "fact": f2},
        {"term": "PMCS", "definition": "โมเดลตรวจสอบย้อนกลับ", "fact": f3},
        {"term": "GMP", "definition": "ไม่อยู่ในข้อเท็จจริง", "fact": f2},
    ]}], REPORT, facts)
    assert [t["term"] for t in blocks[0]["terms"]] == ["GAP", "PMCS"]


def test_diagram_keeps_only_linked_known_steps():
    facts = visuals.facts(REPORT)
    blocks, _ = visuals.check([{"type": "diagram", "kind": "flow", "facts": [_fact(facts, "PMCS")],
        "nodes": [{"id": "farm", "label": "สวน"}, {"id": "pack", "label": "โรงคัดบรรจุ"},
                  {"id": "port", "label": "ท่าเรือ"}, {"id": "Bad Id!", "label": "x"}],
        "edges": [{"from": "farm", "to": "pack"}, {"from": "pack", "to": "port"},
                  {"from": "pack", "to": "nowhere"}, {"from": "farm", "to": "farm"}]}], REPORT, facts)
    [block] = blocks
    assert [n["id"] for n in block["nodes"]] == ["farm", "pack", "port"]
    assert len(block["edges"]) == 2


def test_a_report_without_evidence_gets_no_numbers():
    report = copy.deepcopy(REPORT)
    report["engine"] = "agent"
    for source in report["sources"]:
        source["evidence"] = []
    report["sections"][0]["body"] = "ในปี 2566 ไทยส่งออกทุเรียนสด 929,000 ตัน [1]"
    facts = visuals.facts(report)
    assert facts and all(f["origin"] == "report" for f in facts)
    f = _fact(facts, "2566")
    blocks, dropped = visuals.check([
        {"type": "stat_cards", "items": [{"label": "ส่งออก", "value": 929000, "fact": f}]},
        {"type": "timeline", "events": [{"date": "2566", "label": "a", "fact": f}, {"date": "2566", "label": "b", "fact": f}]},
    ], report, facts)
    assert [b["type"] for b in blocks] == ["timeline"]
    assert dropped[0]["type"] == "stat_cards"


def test_unknown_anchor_goes_to_the_lead_and_blocks_are_capped():
    facts = visuals.facts(REPORT)
    f1 = _fact(facts, "929,000")
    one = {"type": "stat_cards", "anchor": {"section": "nope"}, "items": [{"label": "a", "value": 929000, "fact": f1}]}
    blocks, dropped = visuals.check([one] * (visuals.MAX_BLOCKS + 2), REPORT, facts)
    assert len(blocks) == visuals.MAX_BLOCKS and blocks[0]["anchor"] == "lead"
    assert len(dropped) == 2


def test_text_is_cut_to_size_and_control_characters_go():
    facts = visuals.facts(REPORT)
    f1 = _fact(facts, "929,000")
    [block], _ = visuals.check([{"type": "stat_cards", "title": "x​" * 200,
        "items": [{"label": "<b>ส่งออก</b>\x07", "value": 929000, "fact": f1}]}], REPORT, facts)
    assert len(block["title"]) <= visuals.MAX_TEXT["title"] and "​" not in block["title"]
    # Markup stays text here; the renderer escapes it.
    assert block["items"][0]["label"] == "<b>ส่งออก</b>"


def test_the_file_belongs_to_one_report(tmp_path):
    path = str(tmp_path / "visuals.json")
    visuals.write({"schema": 1, "report": visuals.report_hash(REPORT), "blocks": [], "hidden": []}, path)
    assert visuals.load(path, REPORT) is not None
    changed = copy.deepcopy(REPORT)
    changed["title"] = "อื่น"
    assert visuals.load(path, changed) is None


def test_hidden_blocks_are_known_ones():
    v = {"schema": 1, "blocks": [{"id": "v1"}, {"id": "v2"}], "hidden": []}
    assert visuals.set_hidden(v, ["v2", "v9"])["hidden"] == ["v2"]


def test_page_furniture_and_references_are_not_facts():
    report = copy.deepcopy(REPORT)
    report["sources"][0]["evidence"] = [
        "![logo](https://x.example/l.png) ## Songkran became a soft power strategy by 2023, drawing 500,000 visitors. "
        "See <https://x.example/page> for more.\n"
        "References\nAppadurai, A. (2013). The future as cultural fact. Verso Books.\n"
        "Becker, K. (2020). Revitalizing tradition. Journal of Baltic Studies, 51(3), 342-364."
    ]
    texts = [f["text"] for f in visuals.facts(report) if f["source"] == 1]
    assert any("soft power strategy by 2023" in t for t in texts)
    assert not any("http" in t or "logo" in t or "##" in t for t in texts)
    assert not any("Appadurai" in t or "Becker" in t for t in texts)


def test_a_line_is_not_made_of_citation_years_or_one_repeated_figure():
    report = copy.deepcopy(REPORT)
    report["sources"][0]["evidence"] = [
        "ระหว่าง ค.ศ. 1990-1997 การผลิตเมล็ดพืชเพิ่มเฉลี่ย 1 เปอร์เซ็นต์ต่อปี",
        "อัตราการเพิ่มของประชากรเฉลี่ย 1.3 เปอร์เซ็นต์ (Hinrichsen and Robey, 2000) ซึ่งคล้อยตามทฤษฎีของมัลทัส",
    ]
    facts = visuals.facts(report)
    grain, people = _fact(facts, "1990-1997"), _fact(facts, "Hinrichsen")
    line = {"type": "chart", "chart": "line", "series": [
        {"name": "เมล็ดพืช", "points": [{"x": "1990", "y": 1, "fact": grain}, {"x": "1997", "y": 1, "fact": grain}]},
        {"name": "ประชากร", "points": [{"x": "2000", "y": 1.3, "fact": people}, {"x": "2001", "y": 1.3, "fact": people}]},
    ]}
    blocks, dropped = visuals.check([line], report, facts)
    assert not blocks and dropped[0]["type"] == "chart"
    # Nor is a timeline dated by the paper it cites.
    blocks, _ = visuals.check([{"type": "timeline", "events": [
        {"date": "2000", "label": "a", "fact": people}, {"date": "1990", "label": "b", "fact": grain}]}], report, facts)
    assert not blocks

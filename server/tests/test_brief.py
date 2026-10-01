"""The brief page (litstorm.render.brief): the tiles, the knowledge map, the
reading canvas; nothing from the model run as markup, nothing fetched, only
our scripts run."""

import base64
import hashlib
import json
import re

from litstorm import report as report_mod
from litstorm.render import brief
from test_interactive import _figures, _visuals
from test_visuals import REPORT

SVGS = {"v1": "<svg id='fake-v1'></svg>", "most-cited": "<svg id='fake-mc'></svg>", "by-section": "<svg id='fake-bs'></svg>"}


def _page(v=None, report=REPORT, **kw):
    return brief.render(report, v, svgs=SVGS, **kw)


def _data(page):
    return json.loads(re.search(r'<script type="application/json" id="ls-data">(.*?)</script>', page, re.S).group(1))


def test_the_map_has_every_theme_and_what_backs_it():
    page = _page()
    sections = list(report_mod.walk(REPORT["sections"]))
    for s in sections:
        assert f'data-node="{s["id"]}"' in page
    child = REPORT["sections"][0]["children"][0]
    assert f'data-node="{child["id"]}" data-parent="s1"' in page
    data = _data(page)["map"]
    # A theme counts what its subtopics cite as well as its own text.
    expect = []
    for s in [REPORT["sections"][0], *report_mod.walk(REPORT["sections"][0]["children"])]:
        expect += [str(n) for n in report_mod.cited_ids(s["body"]) if str(n) not in expect]
    assert data["s1"]["sources"] == expect
    assert data["lead"]["heading"] == REPORT["title"]


def test_a_gist_is_plain_words():
    text = "## หัวข้อ\n\nส่งออก **มาก** [1] ตาม [รายงาน](https://example.com) [2]\n\nย่อหน้าสอง"
    assert brief._gist(text) == "ส่งออก มาก ตาม รายงาน"
    long = " ".join(["คำ"] * 200)
    assert len(brief._gist(long)) <= 262 and brief._gist(long).endswith("…")


def test_the_chart_tile_is_the_models_chart_else_a_measure_of_the_report():
    drawn = _page(_visuals(_figures()))
    assert 'id="v1"' in drawn and "fake-v1" in drawn
    plain = _page()
    # One theme is too few to chart: the Sources cited most instead.
    assert "fake-mc" in plain and "fake-bs" not in plain
    many = dict(REPORT, sections=[dict(REPORT["sections"][0], id=f"t{i}", heading=f"ส่วน {i}", children=[]) for i in range(3)])
    assert "fake-bs" in _page(report=many)


def test_what_the_model_wrote_stays_text():
    page = _page(_visuals(_figures()))
    assert "<script>alert(1)</script>" not in page and "<img src=x" not in page


def test_only_our_scripts_run_and_nothing_is_fetched():
    for full in (False, True):
        page = brief.render(REPORT, _visuals(_figures()), svgs=SVGS, full=full)
        markup = re.sub(r"<script\b[^>]*>.*?</script>", "", page, flags=re.S)
        assert not re.search(r"<(link|img|iframe|object|embed|video|audio|source)\b", markup)
        assert not re.search(r"<[^>]+\ssrc=", markup)
        assert not re.search(r"url\((?!data:)", markup)
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        assert "default-src 'none'" in policy and "connect-src" not in policy
        run = re.findall(r"<script>(.*?)</script>", page, re.S)
        assert len(run) == (3 if full else 1)
        for script in run:
            digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in policy
        for data in re.findall(r'<script type="application/json" id="[^"]+">(.*?)</script>', page, re.S):
            assert "</" not in data
        assert ('id="ls-charts"' in page) == full


def test_dark_follows_the_system_or_the_choice_and_print_is_light():
    page = _page()
    assert ':root[data-theme="dark"]' in page and "prefers-color-scheme: dark" in page
    assert 'data-act="theme"' in page
    printed = page[page.index("@media print"):]
    assert "--bg: #eef3fb" in printed

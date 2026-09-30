"""The interactive page (litstorm.render.interactive): figures in place,
nothing from the model run as markup, nothing fetched, only our script run."""

import base64
import hashlib
import os
import re

import pytest

from litstorm import visuals
from litstorm.render import interactive
from test_visuals import REPORT, _fact


def _visuals(blocks, hidden=()):
    facts = visuals.facts(REPORT)
    kept, _ = visuals.check(blocks, REPORT, facts)
    return {"schema": 1, "report": visuals.report_hash(REPORT), "model": "Test Model", "blocks": kept,
            "dropped": [], "hidden": list(hidden)}


def _page(v=None, **kw):
    # Charts as stand-ins: drawing them needs Chromium (see the slow test).
    return interactive.render(REPORT, v, svgs={"v1": "<svg id='fake-v1'></svg>", "most-cited": "<svg id='fake-mc'></svg>"}, **kw)


def _figures():
    facts = visuals.facts(REPORT)
    f1, f2 = _fact(facts, "929,000"), _fact(facts, "๘๒๕")
    return [
        {"type": "chart", "chart": "bar", "anchor": "s2", "title": "ส่งออก", "unit": "ตัน",
         "series": [{"name": "ตัน", "points": [{"x": "2566", "y": 929000, "fact": f1}, {"x": "2565", "y": 825000, "fact": f2}]}]},
        {"type": "stat_cards", "anchor": "lead", "title": "<script>alert(1)</script>",
         "items": [{"label": "<img src=x onerror=alert(1)>", "value": 929000, "unit": "ตัน", "fact": f1}]},
    ]


def test_figures_go_where_they_belong():
    page = _page(_visuals(_figures()))
    # The chart after section s2's own text; the key figures after the overview.
    assert page.index('id="s2"') < page.index('id="v1"')
    assert page.index('id="fig-outline"') < page.index('id="v2"') < page.index('id="s1"')
    assert "fake-v1" in page and "929,000" in page
    assert "Test Model" in page


def test_what_the_model_wrote_stays_text():
    page = _page(_visuals(_figures()))
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x" not in page


def test_hidden_figures_are_left_out():
    page = _page(_visuals(_figures(), hidden=["v1"]))
    assert 'id="v1"' not in page and 'id="v2"' in page


def test_without_visuals_the_report_still_gets_its_own_figures():
    page = _page(None)
    assert 'id="fig-outline"' in page and 'id="fig-most-cited"' in page and "fake-mc" in page
    assert "Test Model" not in page


def test_only_our_scripts_run_and_nothing_is_fetched():
    for full in (False, True):
        page = _page(_visuals(_figures()), full=full)
        # Markup only: the chart library's code mentions src= without fetching.
        # Links to Sources are the one address allowed (they open on a click).
        markup = re.sub(r"<script\b[^>]*>.*?</script>", "", page, flags=re.S)
        assert not re.search(r"<(link|img|iframe|object|embed|video|audio|source)\b", markup)
        assert not re.search(r"<[^>]+\ssrc=", markup)
        assert not re.search(r"url\((?!data:)", markup)
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        assert "default-src 'none'" in policy and "connect-src" not in policy
        run = re.findall(r"<script>(.*?)</script>", page, re.S)
        assert run and len(run) == (3 if full else 1)
        for script in run:
            digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in policy
        # Data scripts are not run, and "</" cannot close them early.
        for data in re.findall(r'<script type="application/json" id="[^"]+">(.*?)</script>', page, re.S):
            assert "</" not in data
        assert ('id="ls-charts"' in page) == full


def test_the_page_is_kept_and_drawn_again_when_its_inputs_change(tmp_path, monkeypatch):
    drawn = []
    monkeypatch.setattr(interactive, "prerender", lambda specs: drawn.append(len(specs)) or ["<svg></svg>"] * len(specs))
    path = str(tmp_path / "report.json")
    v = _visuals(_figures())
    first = interactive.cached(path, REPORT, v)
    assert interactive.cached(path, REPORT, v) == first and len(drawn) == 1
    interactive.cached(path, REPORT, {**v, "hidden": ["v1"]})
    assert len(drawn) == 2
    assert len(list(tmp_path.glob("interactive-static-*.html"))) == 1


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") and not os.environ.get("LITSTORM_PDF_TEST"),
    reason="needs a Chromium: set LITSTORM_PDF_BROWSER_CHANNEL=msedge or LITSTORM_PDF_TEST=1",
)
def test_charts_are_drawn_as_svg():
    v = _visuals(_figures())
    specs = [interactive.chart_spec(v["blocks"][0], "th"), interactive.most_cited_spec(REPORT)[0]]
    svgs = interactive.prerender(specs)
    assert len(svgs) == 2 and all(s.startswith("<svg") and "viewBox" in s for s in svgs)
    assert "929" in svgs[0]

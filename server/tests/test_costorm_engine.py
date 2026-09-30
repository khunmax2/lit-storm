"""Co-STORM's engine, the parts that need no model: its report, its usage,
and what the Discussion page is shown."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.slow  # imports knowledge_storm


def _info(url, title, snippets, uuid):
    from knowledge_storm.interface import Information

    info = Information(url=url, description="", snippets=snippets, title=title)
    info.citation_uuid = uuid
    return info


def _runner(infos):
    kb = SimpleNamespace(info_uuid_to_info_dict={i.citation_uuid: i for i in infos})
    return SimpleNamespace(knowledge_base=kb)


def test_one_page_cited_under_two_numbers_is_one_source_with_both_passages(tmp_path):
    from litstorm.engines.costorm import engine
    from litstorm.engines.storm import normalize

    runner = _runner([
        _info("https://a.test", "A", ["first passage"], 1),
        _info("https://b.test", "B", ["other"], 2),
        _info("https://a.test", "A", ["second passage"], 3),
    ])
    text = "# บทนำ\n\nสงกรานต์ [3] และ [2].\n\n# ประวัติ\n\nเก่าแก่ [1]."
    engine.report_files(runner, text, str(tmp_path))
    report, dropped = normalize.normalize(str(tmp_path), "Songkran", "th")
    engine.promote_lead(report)
    assert dropped == 0
    assert report["lead"] == "สงกรานต์ [1] และ [2]."  # [3] was page A
    assert [s["heading"] for s in report["sections"]] == ["ประวัติ"]
    assert report["sections"][0]["body"] == "เก่าแก่ [1]."
    a = next(s for s in report["sources"] if s["url"] == "https://a.test")
    assert a["id"] == 1 and a["evidence"] == ["first passage", "second passage"]


def test_a_first_section_that_is_not_an_introduction_stays_a_section():
    from litstorm.engines.costorm import engine

    report = {"lead": "", "sections": [{"heading": "History", "body": "x", "children": []}]}
    engine.promote_lead(report)
    assert report["lead"] == "" and len(report["sections"]) == 1


def test_usage_is_summed_per_model_from_the_runners_log():
    from litstorm.engines.costorm import engine

    log = {
        "conv turn: 3 stage": {"lm_usage": {
            "question_answering_lm": {"openrouter/a": {"prompt_tokens": 10, "completion_tokens": 2}},
            "discourse_manage_lm": {"openrouter/b": {"prompt_tokens": 5, "completion_tokens": 1}},
        }},
        "report stage": {"lm_usage": {
            "knowledge_base_lm": {"openrouter/a": {"prompt_tokens": 7, "completion_tokens": 3}},
        }},
    }
    runner = SimpleNamespace(dump_logging_and_reset=lambda: log)
    rm = SimpleNamespace(get_usage_and_reset=lambda: {"SearXNG": 4})
    llm, search = engine._usage(runner, rm)
    assert llm == {
        "openrouter/a": {"prompt_tokens": 17, "completion_tokens": 5},
        "openrouter/b": {"prompt_tokens": 5, "completion_tokens": 1},
    }
    assert search == {"SearXNG": 4}


def test_the_page_sees_who_said_what_and_which_lines_were_the_warm_start():
    from knowledge_storm.dataclass import ConversationTurn, KnowledgeNode

    from litstorm.engines.costorm import engine

    root = KnowledgeNode(name="root")
    child = KnowledgeNode(name="Economy", content=[1, 2], parent=root)
    root.children.append(child)
    turns = [
        ConversationTurn(role="Moderator", raw_utterance="**Q?", utterance_type="Original Question"),
        ConversationTurn(role="Economist: studies prices", raw_utterance="Up [1].", utterance_type="Potential Answer"),
    ]
    runner = SimpleNamespace(
        conversation_history=turns,
        runner_argument=SimpleNamespace(topic="Songkran"),
        knowledge_base=SimpleNamespace(root=root, info_uuid_to_info_dict={1: _info("https://a.test", "A", ["p"], 1)}),
        discourse_manager=SimpleNamespace(experts=[SimpleNamespace(role_name="Economist")]),
    )
    view = engine.view(runner, warmstart_turns=1)
    assert [(t["role"], t["text"], t["warmup"]) for t in view["turns"]] == [
        ("Moderator", "Q?", True), ("Economist", "Up [1].", False)
    ]
    assert view["turns"][1]["role_description"] == "studies prices" and view["turns"][1]["cited"] == [1]
    assert view["mind_map"] == [{"name": "Economy", "count": 2, "children": []}]
    assert view["sources"]["1"]["url"] == "https://a.test" and view["experts"] == ["Economist"]


def test_a_report_without_an_introduction_gets_a_lead_written_for_it(monkeypatch, tmp_path):
    import dspy

    from litstorm.engines.costorm import engine
    from litstorm.engines.storm import normalize

    assert engine.opens_with_introduction("# บทนำ\n\nx") and engine.opens_with_introduction("\n# Introduction\nx")
    assert not engine.opens_with_introduction("# Background and origin\n\nx")

    class Predict:
        def __init__(self, signature):
            pass

        def __call__(self, topic, draft_page):
            assert "Background" in draft_page
            return SimpleNamespace(lead_section="The lead section:\n# Microplastics\nThey are everywhere [2].")

    monkeypatch.setattr(dspy, "Predict", Predict)
    lm = SimpleNamespace(get_usage_and_reset=lambda: {"openrouter/a": {"prompt_tokens": 9, "completion_tokens": 3}})
    runner = _runner([_info("https://a.test", "A", ["p"], 1), _info("https://b.test", "B", ["q"], 2)])
    runner.lm_config = SimpleNamespace(utterance_polishing_lm=lm)
    usage = []
    progress = SimpleNamespace(usage=lambda stage, llm, search: usage.append((stage, llm)))

    text = engine.with_lead(runner, "Microplastics", "# Background and origin\n\nOld [1].", progress)
    engine.report_files(runner, text, str(tmp_path))
    report, _ = normalize.normalize(str(tmp_path), "Microplastics", "en")
    assert report["lead"] == "They are everywhere [1]."  # the heading it opened with is dropped
    assert [s["heading"] for s in report["sections"]] == ["Background and origin"]
    assert report["sections"][0]["body"] == "Old [2]."
    assert usage == [("report", {"openrouter/a": {"prompt_tokens": 9, "completion_tokens": 3}})]

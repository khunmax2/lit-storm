"""Retry ceilings: three tries in all, and none for errors retrying cannot fix."""

import pytest

pytestmark = pytest.mark.slow  # imports knowledge_storm


class _Err(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _model(monkeypatch, errors):
    from litstorm.engines.storm import providers

    model = providers.BoundedGoogleModel(model="gemini/x", api_key="k", timeout=5, max_tokens=10)
    calls = []

    def fail(prompt, **kwargs):
        calls.append(1)
        raise errors.pop(0) if errors else _Err(500)

    monkeypatch.setattr(model, "basic_request", fail)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return model, calls


def test_transient_errors_are_tried_three_times_in_all(monkeypatch):
    model, calls = _model(monkeypatch, [_Err(429), _Err(503), _Err(500)])
    with pytest.raises(_Err):
        model.request("hi")
    assert len(calls) == 3


def test_a_bad_key_is_not_retried(monkeypatch):
    model, calls = _model(monkeypatch, [_Err(401)])
    with pytest.raises(_Err):
        model.request("hi")
    assert len(calls) == 1


def test_litellm_gets_two_retries():
    from litstorm.engines.storm import providers

    lm = providers.build_lm({"provider": "openrouter", "model": "a/b"}, "k", 100, 30)
    assert lm.kwargs["num_retries"] == 2
    assert lm.kwargs["timeout"] == 30

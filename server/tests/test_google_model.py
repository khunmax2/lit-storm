"""knowledge_storm's Gemini adapter: Google's current SDK behind DSPy's LM
contract. Moved from the Streamlit app's tests when the app was removed."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.slow  # imports knowledge_storm


def _reply(text, prompt_tokens, completion_tokens):
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=prompt_tokens, candidates_token_count=completion_tokens),
    )


def test_the_adapter_returns_completions_and_counts_tokens():
    from knowledge_storm.lm import GoogleModel

    with patch("google.genai.Client") as client_class:
        client = client_class.return_value
        client.models.generate_content.return_value = _reply("A concise answer", 7, 4)
        lm = GoogleModel(
            model="gemini/gemini-flash-latest", api_key="test-key",
            max_tokens=500, temperature=1.0, top_p=0.9, num_retries=6,
        )
        assert lm("Prompt") == ["A concise answer"]

    client_class.assert_called_once_with(api_key="test-key")
    call = client.models.generate_content.call_args
    assert call.kwargs["model"] == "gemini-flash-latest"
    assert call.kwargs["contents"] == "Prompt"
    assert call.kwargs["config"].max_output_tokens == 500
    assert call.kwargs["config"].top_p == 0.9
    assert lm.get_usage_and_reset() == {"gemini-flash-latest": {"prompt_tokens": 7, "completion_tokens": 4}}
    assert lm.get_usage_and_reset()["gemini-flash-latest"]["prompt_tokens"] == 0


def test_dspy_predict_can_use_the_adapter():
    import dspy

    from knowledge_storm.lm import GoogleModel

    class Answer(dspy.Signature):
        question = dspy.InputField()
        answer = dspy.OutputField()

    with patch("google.genai.Client") as client_class:
        client_class.return_value.models.generate_content.return_value = _reply("OK", 1, 1)
        lm = GoogleModel("gemini-test", api_key="test-key", max_tokens=100)
        with dspy.settings.context(lm=lm):
            result = dspy.Predict(Answer)(question="Ready?")
    assert result.answer == "OK"

"""Gemini uses Google's current SDK while preserving DSPy's LM contract."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))

from litellm.caching.caching import Cache

_cache_dir = tempfile.TemporaryDirectory()


class _TestCache(Cache):
    def __init__(self, *args, **kwargs):
        kwargs["disk_cache_dir"] = _cache_dir.name
        super().__init__(*args, **kwargs)


with patch("litellm.caching.caching.Cache", _TestCache):
    from knowledge_storm.lm import GoogleModel


class GoogleGenAITests(unittest.TestCase):
    def test_google_adapter_returns_dspy_completions_and_tracks_tokens(self):
        response = SimpleNamespace(
            text="A concise answer",
            usage_metadata=SimpleNamespace(prompt_token_count=7, candidates_token_count=4),
        )
        with patch("google.genai.Client") as client_class:
            client = client_class.return_value
            client.models.generate_content.return_value = response
            lm = GoogleModel(
                model="gemini/gemini-flash-latest", api_key="test-key",
                max_tokens=500, temperature=1.0, top_p=0.9, num_retries=6,
            )
            self.assertEqual(lm("Prompt"), ["A concise answer"])

        client_class.assert_called_once_with(api_key="test-key")
        call = client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-flash-latest")
        self.assertEqual(call.kwargs["contents"], "Prompt")
        config = call.kwargs["config"]
        self.assertEqual(config.max_output_tokens, 500)
        self.assertEqual(config.top_p, 0.9)
        self.assertEqual(lm.get_usage_and_reset(), {
            "gemini-flash-latest": {"prompt_tokens": 7, "completion_tokens": 4}
        })
        self.assertEqual(lm.get_usage_and_reset()["gemini-flash-latest"]["prompt_tokens"], 0)

    def test_app_selects_new_sdk_only_for_gemini(self):
        import demo_util

        with patch.object(demo_util, "GoogleModel") as google_model, patch.object(
            demo_util, "LitellmModel"
        ) as litellm_model:
            demo_util.build_lm("gemini/gemini-flash-latest", 500, {"api_key": "key"})
            google_model.assert_called_once_with(
                model="gemini-flash-latest", max_tokens=500, api_key="key"
            )
            demo_util.build_lm("openai/gpt-4o-mini", 500, {"api_key": "key"})
            litellm_model.assert_called_once_with(
                model="openai/gpt-4o-mini", max_tokens=500, api_key="key"
            )

    def test_legacy_dspy_predict_can_use_new_google_adapter(self):
        import dspy

        class Answer(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        response = SimpleNamespace(
            text="OK", usage_metadata=SimpleNamespace(
                prompt_token_count=1, candidates_token_count=1
            )
        )
        with patch("google.genai.Client") as client_class:
            client_class.return_value.models.generate_content.return_value = response
            lm = GoogleModel("gemini-test", api_key="test-key", max_tokens=100)
            with dspy.settings.context(lm=lm):
                result = dspy.Predict(Answer)(question="Ready?")
        self.assertEqual(result.answer, "OK")


if __name__ == "__main__":
    unittest.main()

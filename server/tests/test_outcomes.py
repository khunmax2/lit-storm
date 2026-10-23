"""Why a Run failed, when the failure reaches us only as text (litstorm.outcomes)."""

import pytest

from litstorm import outcomes


@pytest.mark.parametrize("said, reason", [
    # The Deep Research CLI's last line after the AI SDK gave up (host 203, 2026-10-23).
    ("Failed after 3 attempts. Last error: Too Many Requests", outcomes.RETRIES_EXHAUSTED),
    ("Rate limit exceeded: free-models-per-min", outcomes.RETRIES_EXHAUSTED),
    ("upstream returned 429", outcomes.RETRIES_EXHAUSTED),
    ("Service Unavailable", outcomes.RETRIES_EXHAUSTED),
    ("Bad Gateway", outcomes.RETRIES_EXHAUSTED),
    ("Provider returned error: overloaded", outcomes.RETRIES_EXHAUSTED),
    ("Request timed out", outcomes.RETRIES_EXHAUSTED),
    ("TypeError: fetch failed", outcomes.RETRIES_EXHAUSTED),
    # A spent or wrong key is the administrator's to fix, not a moment's bad luck.
    ('OpenrouterException - {"error":{"message":"Key limit exceeded (total limit).', outcomes.BAD_CONFIGURATION),
    ("Insufficient credits. Add more using https://openrouter.ai/credits", outcomes.BAD_CONFIGURATION),
    ("Payment Required", outcomes.BAD_CONFIGURATION),
    ("Unauthorized", outcomes.BAD_CONFIGURATION),
    ("Incorrect API key provided", outcomes.BAD_CONFIGURATION),
    ("No endpoints found for google/x.", outcomes.BAD_CONFIGURATION),
    # Nothing it names: ours to look at.
    ("the research process exited with 0", outcomes.ENGINE_ERROR),
    ("KeyError: 'markdown'", outcomes.ENGINE_ERROR),
    ("", outcomes.ENGINE_ERROR),
    (None, outcomes.ENGINE_ERROR),
])
def test_a_failure_is_read_from_what_it_says(said, reason):
    assert outcomes.from_message(said) == reason


def test_an_exception_no_class_names_is_read_by_its_message():
    """litellm raised its plain APIError for OpenRouter's "Key limit exceeded" (2026-10)."""
    import litellm

    spent = litellm.APIError(
        status_code=403, message='OpenrouterException - {"error":{"message":"Key limit exceeded (total limit)."}}',
        llm_provider="openrouter", model="openrouter/google/x",
    )
    assert outcomes.classify(spent) == outcomes.BAD_CONFIGURATION
    assert outcomes.classify(KeyError("markdown")) == outcomes.ENGINE_ERROR

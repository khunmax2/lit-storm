"""Why a Run ended, and whether its quota comes back.

The table is docs/web-app-design.md, "ความล้มเหลวกับการคืนโควตา". Costs are
recorded whatever the outcome; this decides only the quota.
"""

SUCCEEDED = "succeeded"
CANCELLED = "cancelled"  # the owner stopped a Run that had started
RETRIES_EXHAUSTED = "retries_exhausted"  # timeouts, 5xx, rate limits
BAD_CONFIGURATION = "bad_configuration"  # wrong key, no credit, unknown model or address
INTERRUPTED = "interrupted"  # the Worker went away
TIMED_OUT = "timed_out"  # past the Run's wall-clock ceiling
EMPTY_REPORT = "empty_report"  # finished, with nothing to read
REFUSED = "refused"  # the model declined the topic
ENGINE_ERROR = "engine_error"  # a fault in our code or the engine's

REFUNDED = {
    RETRIES_EXHAUSTED,
    BAD_CONFIGURATION,
    INTERRUPTED,
    TIMED_OUT,
    EMPTY_REPORT,
    ENGINE_ERROR,
}


def refunds_quota(reason):
    return reason in REFUNDED


def classify(error):
    """The reason for an exception raised out of an Engine."""
    # Imported here so the table above can be read without the engine's
    # dependencies installed.
    import litellm
    import requests
    from litellm.exceptions import PermissionDeniedError

    from knowledge_storm.lm import EmptyCompletionError
    from knowledge_storm.rm import SearXNGConfigError

    if isinstance(error, litellm.ContentPolicyViolationError):
        return REFUSED
    if isinstance(
        error,
        (
            litellm.AuthenticationError,
            PermissionDeniedError,
            litellm.NotFoundError,
            litellm.BudgetExceededError,
            # A setting the model does not accept, e.g. turning off reasoning
            # on a model that always reasons. Retrying sends the same thing.
            litellm.BadRequestError,
            SearXNGConfigError,
            EmptyCompletionError,
        ),
    ):
        return BAD_CONFIGURATION
    if isinstance(
        error,
        (
            litellm.RateLimitError,
            litellm.Timeout,
            litellm.APIConnectionError,
            litellm.ServiceUnavailableError,
            litellm.InternalServerError,
            requests.Timeout,
            requests.ConnectionError,
        ),
    ):
        return RETRIES_EXHAUSTED

    status = _google_status(error)
    if status in (400, 401, 403, 404):
        return BAD_CONFIGURATION
    if status is not None:
        return RETRIES_EXHAUSTED
    return ENGINE_ERROR


def _google_status(error):
    try:
        from google.genai import errors
    except ImportError:
        return None
    if isinstance(error, errors.APIError):
        return getattr(error, "code", None)
    return None

"""Why a Run ended, and whether its quota comes back.

The table is docs/web-app-design.md, "ความล้มเหลวกับการคืนโควตา". Costs are
recorded whatever the outcome; this decides only the quota.
"""

import re

SUCCEEDED = "succeeded"
CANCELLED = "cancelled"  # the owner stopped a Run that had started
RETRIES_EXHAUSTED = "retries_exhausted"  # timeouts, 5xx, rate limits
BAD_CONFIGURATION = "bad_configuration"  # wrong key, no credit, unknown model or address
INTERRUPTED = "interrupted"  # the Worker went away
TIMED_OUT = "timed_out"  # past the Run's wall-clock ceiling
EMPTY_REPORT = "empty_report"  # finished, with nothing to read
TRUNCATED_REPORT = "truncated_report"  # the model stopped writing part-way, twice (litstorm.completeness)
REFUSED = "refused"  # the model declined the topic
ENGINE_ERROR = "engine_error"  # a fault in our code or the engine's
# A remote Engine's service (catalog.remote, docs/adr/0013):
SERVICE_UNAVAILABLE = "service_unavailable"  # unreachable, or busy past the Run's time
SERVICE_DECLINED = "service_declined"  # it would not take the question, e.g. a medical emergency

REFUNDED = {
    RETRIES_EXHAUSTED,
    BAD_CONFIGURATION,
    INTERRUPTED,
    TIMED_OUT,
    EMPTY_REPORT,
    TRUNCATED_REPORT,
    ENGINE_ERROR,
    SERVICE_UNAVAILABLE,
    SERVICE_DECLINED,  # nothing was spent
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
    # litellm's plain APIError, say, which OpenRouter's "Key limit exceeded" came as.
    return from_message(str(error))


# What a failure says, for the failures that reach us only as text: the Deep
# Research CLI's error line, a review MRA reports failed, an exception none of
# the classes above names. A spent key is checked first: it too says "limit".
_SAID = (
    (BAD_CONFIGURATION, re.compile(
        r"key limit exceeded|insufficient (credits|quota|balance)|payment required|\b40[12]\b|unauthori[sz]ed"
        r"|(invalid|incorrect) api key|no endpoints found|model not found|not a valid model", re.I)),
    (RETRIES_EXHAUSTED, re.compile(
        r"too many requests|rate[ -]?limit|\b(429|50[234])\b|overloaded|service unavailable|bad gateway"
        r"|gateway timeout|timed? ?out|econnreset|fetch failed", re.I)),
)


def from_message(said, default=ENGINE_ERROR):
    """The reason a failure's own words give, or `default` when they name none."""
    for reason, pattern in _SAID:
        if said and pattern.search(said):
            return reason
    return default


def _google_status(error):
    try:
        from google.genai import errors
    except ImportError:
        return None
    if isinstance(error, errors.APIError):
        return getattr(error, "code", None)
    return None

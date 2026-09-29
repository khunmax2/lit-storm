"""What every Engine is given, and what it hands back.

An Engine runs inside the subprocess of one Run (docs/adr/0003) and knows
nothing about queues, quota or the database. It is given the Run's settings,
a directory of its own, somewhere to say how far it has got, and a way to
learn that the owner has asked it to stop (docs/adr/0004).
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class RunConfig:
    """The settings one Run was started with — the config snapshot.

    Nothing here is secret; this is what the owner may see and what is kept
    with the Run. Credentials travel separately, in `Secrets`.
    """

    run_id: str
    engine: str
    topic: str
    language: str  # report language: "th" | "en"
    llm: dict[str, Any]  # {"provider", "model", optional "api_base", "reasoning"}
    search: dict[str, Any]  # {"provider", optional "endpoint", "engines"}
    params: dict[str, Any] = field(default_factory=dict)  # engine knobs, set by admins
    # The model for research's short calls, like `llm` plus "max_tokens";
    # empty: `llm` does everything (docs/adr/0006).
    fast_llm: dict[str, Any] = field(default_factory=dict)
    # {"provider", "model", "api_base"}; empty or "builtin" is STORM's own model.
    embedding: dict[str, Any] = field(default_factory=dict)
    request_timeout: float = 120.0  # seconds, per LLM or search request
    # The depth level's time target. At 80% of it an Engine stops gathering
    # and writes from what it has (docs/web-app-design.md, จบอย่างนุ่มนวล).
    target_seconds: float | None = None
    # Where search results are shared between Runs (litstorm.search_cache);
    # None searches afresh every time.
    search_cache_dir: str | None = None
    # The owner's answers to the clarifying questions: [{"question", "answer"}].
    refinement: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass(frozen=True)
class Secrets:
    """Credentials for one Run. Never written into the Run's directory."""

    llm_api_key: str = ""
    search_api_key: str = ""
    embedding_api_key: str = ""
    fast_llm_api_key: str = ""

    def __repr__(self):
        return "Secrets(<redacted>)"


class Cancelled(Exception):
    """The owner asked the Run to stop, and it reached a point where it could."""


class CancelToken(Protocol):
    def requested(self) -> bool: ...

    def check(self) -> None:
        """Raise Cancelled if a stop has been asked for."""


class Progress(Protocol):
    def stage(self, name: str) -> None:
        """A stage has started. Stages are the points a Run can stop at."""

    def note(self, kind: str, **data: Any) -> None:
        """Something the owner may want to see while waiting."""

    def usage(self, stage: str, llm: dict, search: dict) -> None:
        """Tokens per model and queries per search provider for one stage."""


class Engine(Protocol):
    name: str

    def run(
        self,
        config: RunConfig,
        secrets: Secrets,
        workspace: str,
        progress: Progress,
        cancel: CancelToken,
    ) -> dict:
        """Do the research and return a report (see litstorm.report).

        Raise Cancelled when `cancel` says so; whatever the finished stages
        wrote to `workspace` is kept.
        """


class EngineFailure(Exception):
    """The Run failed, with a reason from `litstorm.outcomes`."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason

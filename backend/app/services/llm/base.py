from abc import ABC, abstractmethod


class LLMUnavailableError(Exception):
    pass


class LLMQuotaExceededError(LLMUnavailableError):
    """The provider reported quota/rate-limit exhaustion (HTTP 429) specifically,
    as opposed to a generic failure — lets callers surface a distinct, actionable
    message instead of a generic "LLM unavailable" one."""


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, prompt: str, schema_hint: str, timeout: int = 30) -> dict:
        pass

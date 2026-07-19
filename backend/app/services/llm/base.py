from abc import ABC, abstractmethod


class LLMUnavailableError(Exception):
    pass


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, prompt: str, schema_hint: str, timeout: int = 30) -> dict:
        pass

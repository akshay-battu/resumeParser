from app.services.llm.base import LLMClient, LLMUnavailableError
from app.services.llm.langchain_gemini import LangChainGeminiClient


def _cfg(config, key: str, default: str = "") -> str:
    if hasattr(config, "get"):
        return config.get(key, default)
    return getattr(config, key, default)


def get_llm_client(provider: str, config) -> LLMClient:
    provider = (provider or "gemini").lower()

    if provider == "gemini":
        return LangChainGeminiClient(
            api_key=_cfg(config, "GEMINI_API_KEY"),
            model_name=_cfg(config, "GEMINI_MODEL", "gemini-3.5-flash"),
        )

    raise LLMUnavailableError(f"Unsupported LLM provider: {provider}")

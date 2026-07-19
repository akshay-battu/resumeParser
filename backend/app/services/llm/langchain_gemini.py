import json
import re

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.llm.base import LLMClient, LLMUnavailableError


def _extract_text(content) -> str:
    """
    Safely extract text from LangChain response content.
    Newer Gemini models return content as a list of dicts:
      [{'type': 'text', 'text': '...', 'extras': {...}}, ...]
    Older versions may return a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                # Structured content block — extract the 'text' field
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


class LangChainGeminiClient(LLMClient):
    """LangChain-backed Gemini client — keeps business logic provider-agnostic."""

    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash"):
        if not api_key:
            raise LLMUnavailableError("GEMINI_API_KEY is not configured")
        self.llm = ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model_name,
            temperature=0.1,
            response_mime_type="application/json",
        )

    def complete_json(self, prompt: str, schema_hint: str, timeout: int = 60) -> dict:
        full_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON only, no markdown fences. Schema:\n{schema_hint}"
        )
        try:
            response = self.llm.invoke(
                [HumanMessage(content=full_prompt)],
                config={"timeout": timeout},
            )
            text = _extract_text(response.content or "{}")

            # Strip markdown fences if model wraps the JSON anyway
            match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1)

            text = text.strip()

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Fallback: handle Python-style single-quoted dicts
                import ast
                return ast.literal_eval(text)
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

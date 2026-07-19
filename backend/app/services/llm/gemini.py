import json
import re

import google.generativeai as genai

from app.services.llm.base import LLMClient, LLMUnavailableError


class GeminiLLMClient(LLMClient):
    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash"):
        if not api_key:
            raise LLMUnavailableError("GEMINI_API_KEY is not configured")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def complete_json(self, prompt: str, schema_hint: str, timeout: int = 60) -> dict:
        full_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON only, no markdown fences. Schema:\n{schema_hint}"
        )
        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": timeout},
            )
            text = response.text or "{}"
            text = re.sub(r"^```json\s*", "", text.strip())
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

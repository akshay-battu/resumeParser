import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.services.llm.base import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s\-().]{7,20}$")

PARSE_SCHEMA_HINT = """{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "company": "string or null",
  "designation": "string or null",
  "skills": ["string"],
  "confidence": {
    "name": 0.0-1.0,
    "email": 0.0-1.0,
    "phone": 0.0-1.0,
    "company": 0.0-1.0,
    "designation": 0.0-1.0,
    "skills": 0.0-1.0
  }
}"""


class ConfidenceScores(BaseModel):
    name: float = Field(default=0.0, ge=0.0, le=1.0)
    email: float = Field(default=0.0, ge=0.0, le=1.0)
    phone: float = Field(default=0.0, ge=0.0, le=1.0)
    company: float = Field(default=0.0, ge=0.0, le=1.0)
    designation: float = Field(default=0.0, ge=0.0, le=1.0)
    skills: float = Field(default=0.0, ge=0.0, le=1.0)


class ParsedResume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    designation: str | None = None
    skills: list[str] = Field(default_factory=list)
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)


def _apply_heuristic_boost(parsed: ParsedResume) -> ParsedResume:
    """
    Hybrid confidence approach: start from LLM self-reported certainty, then
    boost fields that pass simple format validation (email/phone regex).
    Inferred or missing fields keep lower LLM scores.
    """
    conf = parsed.confidence.model_copy()

    if parsed.email and EMAIL_RE.match(parsed.email.strip()):
        conf.email = max(conf.email, 0.9)
    if parsed.phone and PHONE_RE.match(parsed.phone.strip()):
        conf.phone = max(conf.phone, 0.9)
    if parsed.name:
        conf.name = max(conf.name, 0.5)

    parsed.confidence = conf
    return parsed


def _fallback_result() -> dict[str, Any]:
    low = 0.1
    return {
        "name": None,
        "email": None,
        "phone": None,
        "company": None,
        "designation": None,
        "skills": [],
        "confidence": {
            "name": low,
            "email": low,
            "phone": low,
            "company": low,
            "designation": low,
            "skills": low,
        },
    }


def parse_resume_text(raw_text: str, llm: LLMClient) -> dict[str, Any]:
    if not raw_text or not raw_text.strip():
        return _fallback_result()

    prompt = (
        "Extract structured candidate information from this resume text. "
        "For each field, include a confidence score (0-1) reflecting how certain "
        "you are based on explicit mentions vs inference.\n\n"
        f"RESUME TEXT:\n{raw_text[:12000]}"
    )

    last_error = None
    for attempt in range(2):
        try:
            data = llm.complete_json(prompt, PARSE_SCHEMA_HINT)
            parsed = ParsedResume.model_validate(data)
            parsed = _apply_heuristic_boost(parsed)
            return {
                "name": parsed.name,
                "email": parsed.email,
                "phone": parsed.phone,
                "company": parsed.company,
                "designation": parsed.designation,
                "skills": parsed.skills,
                "confidence": parsed.confidence.model_dump(),
            }
        except (ValidationError, LLMUnavailableError) as exc:
            last_error = exc
            logger.warning("Resume parse attempt %s failed: %s", attempt + 1, exc)

    logger.error("Resume parsing failed after retry: %s", last_error)
    return _fallback_result()

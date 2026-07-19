import logging

from app.services.llm.base import LLMClient, LLMQuotaExceededError, LLMUnavailableError

logger = logging.getLogger(__name__)


def _fallback_message(
    name: str | None,
    company: str | None,
    designation: str | None,
    channel: str = "email",
) -> str:
    """Template fallback when the LLM is slow or unavailable."""
    candidate_name = name or "there"
    org = company or "your organization"
    role = designation or "the role you applied for"
    medium = "email" if channel == "email" else "message"

    return (
        f"Dear {candidate_name},\n\n"
        f"Congratulations on progressing in our hiring process for the {role} "
        f"position. As part of standard KYC and background verification, we "
        f"kindly request copies of your PAN card and Aadhaar card.\n\n"
        f"We understand you are currently associated with {org}, and we want "
        f"to make this step as smooth as possible. Please reply to this "
        f"{medium} with clear scans or photos of both documents at your "
        f"earliest convenience.\n\n"
        f"Your documents will be handled securely and used only for "
        f"verification purposes.\n\n"
        f"Thank you,\n"
        f"ResumeParser HR Team"
    )


class DocumentRequestAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate_request(
        self,
        name: str | None,
        email: str | None,
        phone: str | None,
        company: str | None,
        designation: str | None,
        channel: str = "email",
    ) -> str:
        candidate_name = name or "there"
        prompt = (
            f"Write a professional, warm {channel} message to a job candidate "
            f"requesting their PAN card and Aadhaar card copies for KYC and "
            f"background verification as part of the hiring process.\n\n"
            f"Candidate context:\n"
            f"- Name: {candidate_name}\n"
            f"- Email: {email or 'unknown'}\n"
            f"- Phone: {phone or 'unknown'}\n"
            f"- Current/Recent company: {company or 'their current organization'}\n"
            f"- Role: {designation or 'the applied position'}\n\n"
            "Requirements:\n"
            "- Personalize naturally using their name, company, and role\n"
            "- Explain why PAN and Aadhaar are needed (KYC/background verification)\n"
            "- Give clear next steps for secure submission\n"
            "- Keep tone professional but friendly, not a generic template\n"
            "- Do NOT use placeholder brackets like [Name]\n"
            "- Return JSON with a single key 'message' containing the full text"
        )
        schema = '{"message": "string"}'

        last_error = None
        for attempt in range(2):
            try:
                result = self.llm.complete_json(prompt, schema, timeout=60)
                message = result.get("message", "").strip()
                if message:
                    return message
                last_error = LLMUnavailableError("Empty message from LLM")
            except LLMQuotaExceededError:
                # Don't retry or fall back — quota exhaustion won't clear up on
                # the next attempt, and the caller needs the specific error to
                # surface an actionable message instead of a generic template.
                raise
            except LLMUnavailableError as exc:
                last_error = exc
                logger.warning("Document request attempt %s failed: %s", attempt + 1, exc)

        logger.warning("Using fallback document request template: %s", last_error)
        return _fallback_message(name, company, designation, channel)

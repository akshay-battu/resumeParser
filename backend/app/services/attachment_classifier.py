import logging

from app.services.llm.base import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

CLASSIFY_SCHEMA = """{
  "pan_index": 0,
  "aadhaar_index": 1,
  "confidence": 0.0-1.0
}"""


def classify_attachments(filenames: list[str], llm: LLMClient) -> dict:
    """
    Use LangChain LLM to classify which attachment is PAN vs Aadhaar by filename.
    Falls back to positional guess if LLM fails.
    """
    if not filenames:
        return {"pan_index": None, "aadhaar_index": None, "confidence": 0.0}

    if len(filenames) == 1:
        name = filenames[0].lower()
        if "aadhaar" in name or "aadhar" in name:
            return {"pan_index": None, "aadhaar_index": 0, "confidence": 0.7}
        if "pan" in name:
            return {"pan_index": 0, "aadhaar_index": None, "confidence": 0.7}
        return {"pan_index": 0, "aadhaar_index": None, "confidence": 0.3}

    listing = "\n".join(f"{i}: {name}" for i, name in enumerate(filenames))
    prompt = (
        "Classify identity document attachments for an Indian KYC process.\n"
        "Given these filenames (index: name), identify which is the PAN card "
        "and which is the Aadhaar card.\n\n"
        f"Attachments:\n{listing}\n\n"
        "Return pan_index and aadhaar_index as 0-based indices, or null if unclear."
    )

    try:
        result = llm.complete_json(prompt, CLASSIFY_SCHEMA, timeout=30)
        pan_idx = result.get("pan_index")
        aadhaar_idx = result.get("aadhaar_index")
        if pan_idx is not None and not isinstance(pan_idx, int):
            pan_idx = int(pan_idx)
        if aadhaar_idx is not None and not isinstance(aadhaar_idx, int):
            aadhaar_idx = int(aadhaar_idx)
        return {
            "pan_index": pan_idx,
            "aadhaar_index": aadhaar_idx,
            "confidence": float(result.get("confidence", 0.8)),
        }
    except (LLMUnavailableError, ValueError, TypeError) as exc:
        logger.warning("Attachment classification fallback: %s", exc)
        return _filename_heuristic(filenames)


def _filename_heuristic(filenames: list[str]) -> dict:
    pan_idx = aadhaar_idx = None
    for i, name in enumerate(filenames):
        lower = name.lower()
        if pan_idx is None and "pan" in lower:
            pan_idx = i
        if aadhaar_idx is None and ("aadhaar" in lower or "aadhar" in lower):
            aadhaar_idx = i

    remaining = [i for i in range(len(filenames)) if i not in (pan_idx, aadhaar_idx)]
    if pan_idx is None and remaining:
        pan_idx = remaining.pop(0)
    if aadhaar_idx is None and remaining:
        aadhaar_idx = remaining.pop(0)

    return {"pan_index": pan_idx, "aadhaar_index": aadhaar_idx, "confidence": 0.5}

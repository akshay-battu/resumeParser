from pathlib import Path

from docx import Document
from pypdf import PdfReader


class ResumeExtractionError(Exception):
    pass


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)

    raise ResumeExtractionError(f"Unsupported file type: {ext}")


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _extract_docx(path: Path) -> str:
    doc = Document(str(path))
    parts = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(parts).strip()

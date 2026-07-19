"""Generate a sample resume PDF for testing."""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_sample_resume(output_path: str):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 72

    lines = [
        "PRIYA SHARMA",
        "Software Engineer",
        "",
        "Email: priya.sharma@emaildemo.com",
        "Phone: +91 98765 43210",
        "",
        "EXPERIENCE",
        "Senior Developer — TechNova Solutions (2021 – Present)",
        "Built scalable APIs and led a team of 4 engineers.",
        "",
        "SKILLS",
        "Python, Flask, React, SQL, REST APIs, Docker",
    ]

    for line in lines:
        c.drawString(72, y, line)
        y -= 20

    c.save()
    print(f"Created {path}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    out = root / "samples" / "sample_resume.pdf"
    generate_sample_resume(str(out))

"""Seed database with a demo candidate (no LLM required)."""
from app import create_app
from app.extensions import db
from app.models.candidate import Candidate


def seed():
    app = create_app()
    with app.app_context():
        existing = Candidate.query.filter_by(email="priya.sharma@emaildemo.com").first()
        if existing:
            print("Seed candidate already exists.")
            return

        candidate = Candidate(
            filename="sample_resume.pdf",
            resume_path="samples/sample_resume.pdf",
            name="Priya Sharma",
            email="priya.sharma@emaildemo.com",
            phone="+91 98765 43210",
            company="TechNova Solutions",
            designation="Senior Developer",
            skills=["Python", "Flask", "React", "SQL", "REST APIs", "Docker"],
            field_confidence={
                "name": 0.95,
                "email": 0.98,
                "phone": 0.92,
                "company": 0.88,
                "designation": 0.85,
                "skills": 0.9,
            },
            raw_text="Priya Sharma - Software Engineer at TechNova Solutions",
            status="parsed",
        )
        db.session.add(candidate)
        db.session.commit()
        print(f"Seeded candidate id={candidate.id}")


if __name__ == "__main__":
    seed()

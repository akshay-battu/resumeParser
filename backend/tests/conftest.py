import io

import pytest

from app import create_app
from app.config import Config
from app.extensions import db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = "test_uploads"
    GEMINI_API_KEY = "test-key"


@pytest.fixture
def app(tmp_path):
    TestConfig.UPLOAD_FOLDER = str(tmp_path / "uploads")
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_pdf():
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 720, "Priya Sharma")
    c.drawString(72, 700, "priya.sharma@emaildemo.com")
    c.drawString(72, 680, "TechNova Solutions")
    c.save()
    buf.seek(0)
    return buf

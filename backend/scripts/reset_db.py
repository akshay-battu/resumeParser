#!/usr/bin/env python3
"""
DB Reset Script — clears all candidate data and uploaded files.
Usage: docker exec assignment-copy-app-1 python /app/scripts/reset_db.py
   Or locally (from backend/): python scripts/reset_db.py
"""
import os
import shutil
import sys

# Allow running from project root or backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
except ImportError:
    pass

from app import create_app
from app.extensions import db
from app.models.candidate import Candidate
from app.models.document_request import DocumentRequest


def reset_db():
    app = create_app()
    with app.app_context():
        print("=== ResumeParser DB Reset ===\n")

        # Count existing data
        candidates = Candidate.query.all()
        doc_requests = DocumentRequest.query.all()
        print(f"Found: {len(candidates)} candidates, {len(doc_requests)} document requests")

        if not candidates and not doc_requests:
            print("Database is already empty. Nothing to do.")
            return

        confirm = input(f"\nAre you sure you want to DELETE ALL DATA? Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

        # Delete uploaded files
        upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
        deleted_files = 0
        if os.path.exists(upload_folder):
            for root, dirs, files in os.walk(upload_folder):
                for f in files:
                    fpath = os.path.join(root, f)
                    try:
                        os.remove(fpath)
                        deleted_files += 1
                    except OSError as e:
                        print(f"  Warning: Could not delete {fpath}: {e}")

        # Drop and recreate all tables
        db.session.query(DocumentRequest).delete()
        db.session.query(Candidate).delete()
        db.session.commit()

        print(f"\n✅ Cleared {len(candidates)} candidates")
        print(f"✅ Cleared {len(doc_requests)} document requests")
        print(f"✅ Deleted {deleted_files} uploaded files")
        print("\nDatabase is now fresh and empty.")


if __name__ == "__main__":
    reset_db()

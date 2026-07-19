#!/usr/bin/env python
"""Copy frontend dist into backend/app/static for production serving."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
dist = ROOT / "frontend" / "dist"
static = ROOT / "backend" / "app" / "static"

if not dist.exists():
    raise SystemExit("Run 'npm run build' in frontend/ first.")

if static.exists():
    shutil.rmtree(static)
shutil.copytree(dist, static)
print(f"Copied {dist} -> {static}")

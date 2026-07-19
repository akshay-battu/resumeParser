from pathlib import Path

from flask import request, send_from_directory


def _frontend_dist() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent / "static",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    ]
    return next((p for p in candidates if p.exists()), None)


def wants_spa() -> bool:
    """Browser navigations prefer HTML; API clients (axios) prefer JSON."""
    if request.method != "GET":
        return False
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "text/html"


def serve_spa():
    dist = _frontend_dist()
    if not dist:
        return {"error": "Frontend not built"}, 404
    return send_from_directory(dist, "index.html")

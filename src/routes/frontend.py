import os
from pathlib import Path

from flask import Blueprint, send_from_directory

DIST_DIR = str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")

frontend = Blueprint("frontend", __name__)

@frontend.route('/', defaults={'path': ''})
@frontend.route('/<path:path>')
def serve_react(path):
    print(f"Requested: {path}")
    print(f"Looking in: {DIST_DIR}")

    full_path = os.path.join(DIST_DIR, path)
    print(f"Full path: {full_path}, exists: {os.path.exists(full_path)}")

    if path and os.path.exists(full_path):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, 'index.html')
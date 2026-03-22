from flask import Blueprint, jsonify
from src.database import get_data_db as get_db


health = Blueprint("health", __name__)


@health.route("/api/")
def ping():
    return jsonify({"ping": "pong"}), 200


@health.route("/api/health")
def health_check():
    """Health check endpoint with database connectivity test."""
    try:
        db = get_db()
        # Test database connectivity and get counts
        paper_count = db.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        author_count = db.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
        microtopic_count = db.execute("SELECT COUNT(*) FROM microtopics").fetchone()[0]

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "paper_count": paper_count,
            "author_count": author_count,
            "microtopic_count": microtopic_count
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 503


@health.route("/api/health/<message>")
def health_check_message(message):
    return jsonify({"response": message}), 200

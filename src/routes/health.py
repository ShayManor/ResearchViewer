from flask import Blueprint, jsonify
from src.database import get_db, DATABASE_PATH


health = Blueprint("health", __name__)


@health.route("/api/")
def ping():
    return jsonify({"ping": "pong"}), 200


@health.route("/api/health")
def health_check():
    """Health check endpoint with database connectivity test."""
    try:
        db = get_db()
        # Test database connectivity
        result = db.execute("SELECT COUNT(*) FROM papers").fetchone()
        paper_count = result[0]

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "database_path": DATABASE_PATH,
            "paper_count": paper_count
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

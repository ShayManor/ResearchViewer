from flask import Blueprint, jsonify


health = Blueprint("health", __name__)


@health.route("/api/")
def ping():
    return jsonify({"ping": "pong"}, 200)


@health.route("/api/health/<message>")
def health_check(message):
    return jsonify({"response": message}, 200)

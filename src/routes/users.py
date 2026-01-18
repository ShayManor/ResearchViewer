from flask import Blueprint

users = Blueprint("users", __name__)


@users.route("/api/users/register", methods=["POST"])
def register():
    """Create new user. Input: username, password."""
    pass


@users.route("/api/users/login", methods=["POST"])
def login():
    """Authenticate user. Input: username, password. Returns: session token."""
    pass


@users.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get user profile. Returns: username, read_papers, subjects_of_interest."""
    pass


@users.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Remove user and all associated data."""
    pass


@users.route("/api/users/<int:user_id>/subjects", methods=["POST"])
def add_subject(user_id):
    """Add subject to user interests. Input: subject."""
    pass


@users.route("/api/users/<int:user_id>/subjects/<subject>", methods=["DELETE"])
def remove_subject(user_id, subject):
    """Remove subject from user interests."""
    pass


@users.route("/api/users/<int:user_id>/read", methods=["POST"])
def add_read_paper(user_id):
    """Add paper to read list. Input: doi."""
    pass


@users.route("/api/users/<int:user_id>/read/<path:doi>", methods=["DELETE"])
def remove_read_paper(user_id, doi):
    """Remove paper from read list."""
    pass


@users.route("/api/users/<int:user_id>/recommendations", methods=["GET"])
def get_recommendations(user_id):
    """Get recommended papers based on read history and subjects. Query params: limit (default 10)."""
    pass

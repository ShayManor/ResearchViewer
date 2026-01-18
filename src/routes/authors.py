from flask import Blueprint

authors = Blueprint("authors", __name__)


@authors.route("/api/authors", methods=["GET"])
def get_authors():
    """Get all authors with optional filters (name search, subject). Supports pagination."""
    pass


@authors.route("/api/authors/search", methods=["GET"])
def search_authors():
    """Search authors by partial name match. Returns list of candidates."""
    pass


@authors.route("/api/authors/<path:author_id>", methods=["GET"])
def get_author(author_id):
    """Get author by OpenAlex/ORCID ID. Returns: name, papers, h-index, website, title, image."""
    pass


@authors.route("/api/authors", methods=["POST"])
def add_author():
    """Add new author. Input: author_id, name, website (optional), title (optional), image (optional)."""
    pass


@authors.route("/api/authors/<path:author_id>", methods=["PUT"])
def update_author(author_id):
    """Update existing author. Input: fields to update."""
    pass


@authors.route("/api/authors/<path:author_id>", methods=["DELETE"])
def delete_author(author_id):
    """Remove author from database."""
    pass


@authors.route("/api/authors/generate", methods=["POST"])
def generate_author():
    """Auto-populate author info from ID. Input: author_id (OpenAlex/ORCID). Returns: name, papers, h-index."""
    pass

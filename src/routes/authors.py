from flask import Blueprint, request, jsonify
from src.database import get_data_db as get_db, df_to_json_serializable
from src.sql_safety import (
    InvalidParameter,
    escape_like,
    safe_int,
    safe_sort_field,
    safe_sort_order,
)

authors_bp = Blueprint("authors", __name__)


@authors_bp.route("/api/authors", methods=["GET"])
def get_authors():
    """Get all authors with optional filters (name search, subject). Supports pagination."""
    db = get_db()

    try:
        page = safe_int(request.args.get('page'), default=1, minimum=1)
        per_page = safe_int(
            request.args.get('per_page'), default=20, minimum=1, maximum=100
        )
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400

    name = request.args.get('name')
    sort_by = safe_sort_field(
        request.args.get('sort_by'),
        allowed=('cited_by_count', 'h_index', 'works_count', 'name'),
        default='cited_by_count',
    )
    sort_order = safe_sort_order(request.args.get('sort_order'))

    query = "SELECT * FROM authors"
    params = []

    if name:
        query += " WHERE name ILIKE ? ESCAPE '\\'"
        params.append(f"%{escape_like(name)}%")

    query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
    params.append(per_page)
    params.append((page - 1) * per_page)

    result = db.execute(query, params).fetchdf()

    return jsonify({
        "authors": df_to_json_serializable(result),
        "page": page,
        "per_page": per_page
    })


@authors_bp.route("/api/authors/search", methods=["GET"])
def search_authors():
    """Search authors by partial name match with optional filters."""
    db = get_db()

    name_query = request.args.get('name', '')
    min_h_index = request.args.get('min_h_index')
    min_works = request.args.get('min_works')
    sort_by = request.args.get('sort_by', 'cited_by_count')
    sort_order = request.args.get('sort_order', 'DESC')
    limit = min(int(request.args.get('limit', 10)), 50)

    if not name_query:
        return jsonify({"error": "Name query parameter is required"}), 400

    # Validate sort field
    allowed_sorts = ['cited_by_count', 'h_index', 'works_count', 'name']
    if sort_by not in allowed_sorts:
        sort_by = 'cited_by_count'

    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    # Build query
    query = """
        SELECT author_id, name, h_index, works_count, cited_by_count
        FROM authors
        WHERE name ILIKE ?
    """
    params = [f"%{name_query}%"]

    if min_h_index:
        query += " AND h_index >= ?"
        params.append(int(min_h_index))

    if min_works:
        query += " AND works_count >= ?"
        params.append(int(min_works))

    query += f" ORDER BY {sort_by} {sort_order} LIMIT ?"
    params.append(limit)

    result = db.execute(query, params).fetchdf()

    return jsonify({
        "authors": df_to_json_serializable(result),
        "count": len(result)
    })


@authors_bp.route("/api/authors/<path:author_id>", methods=["GET"])
def get_author(author_id):
    """Get full author details with aggregated statistics."""
    db = get_db()

    # Get basic author info
    result = db.execute(
        "SELECT * FROM authors WHERE author_id = ?",
        [author_id]
    ).fetchdf()

    if result.empty:
        return jsonify({"error": "Author not found"}), 404

    author = df_to_json_serializable(result)[0]

    # Get author's papers
    paper_dois = author.get('paper_dois', [])

    if paper_dois:
        placeholders = ','.join(['?'] * len(paper_dois))

        # Get top papers by citations
        top_papers = db.execute(f"""
            SELECT id, title, citation_count, update_date
            FROM papers
            WHERE id IN ({placeholders})
            AND (deleted = false OR deleted IS NULL)
            ORDER BY citation_count DESC
            LIMIT 10
        """, paper_dois).fetchdf()

        author['top_papers'] = df_to_json_serializable(top_papers)

        # Papers by year
        papers_by_year = db.execute(f"""
            SELECT
                strftime(update_date, '%Y') as year,
                COUNT(*) as count
            FROM papers
            WHERE id IN ({placeholders})
            AND update_date IS NOT NULL
            AND (deleted = false OR deleted IS NULL)
            GROUP BY year
            ORDER BY year
        """, paper_dois).fetchdf()

        author['papers_by_year'] = df_to_json_serializable(papers_by_year)

        # Citations by year (sum of citations for papers published in each year)
        citations_by_year = db.execute(f"""
            SELECT
                strftime(update_date, '%Y') as year,
                SUM(citation_count) as citations
            FROM papers
            WHERE id IN ({placeholders})
            AND update_date IS NOT NULL
            AND (deleted = false OR deleted IS NULL)
            GROUP BY year
            ORDER BY year
        """, paper_dois).fetchdf()

        author['citations_by_year'] = df_to_json_serializable(citations_by_year)

        # Primary topics
        primary_topics = db.execute(f"""
            SELECT
                primary_topic_name as topic_name,
                COUNT(*) as paper_count
            FROM papers
            WHERE id IN ({placeholders})
            AND primary_topic_name IS NOT NULL
            AND (deleted = false OR deleted IS NULL)
            GROUP BY primary_topic_name
            ORDER BY paper_count DESC
            LIMIT 10
        """, paper_dois).fetchdf()

        author['primary_topics'] = df_to_json_serializable(primary_topics)
    else:
        author['top_papers'] = []
        author['papers_by_year'] = []
        author['citations_by_year'] = []
        author['primary_topics'] = []

    return jsonify(author)


@authors_bp.route("/api/authors", methods=["POST"])
def add_author():
    """Add new author. Input: author_id, name, website (optional), title (optional), image (optional)."""
    db = get_db()
    data = request.get_json()

    # Validate required fields
    if not data.get('author_id'):
        return jsonify({"error": "author_id is required"}), 400

    if not data.get('name'):
        return jsonify({"error": "name is required"}), 400

    # Check if author already exists
    existing = db.execute(
        "SELECT COUNT(*) FROM authors WHERE author_id = ?",
        [data['author_id']]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"error": "Author with this ID already exists"}), 409

    # Insert author
    db.execute("""
        INSERT INTO authors (
            author_id, name, paper_dois, h_index, works_count, cited_by_count
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, [
        data.get('author_id'),
        data.get('name'),
        data.get('paper_dois', []),
        data.get('h_index', 0),
        data.get('works_count', 0),
        data.get('cited_by_count', 0)
    ])

    return jsonify({"status": "created", "author_id": data['author_id']}), 201


@authors_bp.route("/api/authors/<path:author_id>", methods=["PUT"])
def update_author(author_id):
    """Update existing author. Input: fields to update."""
    db = get_db()
    data = request.get_json()

    # Check if author exists
    existing = db.execute(
        "SELECT COUNT(*) FROM authors WHERE author_id = ?",
        [author_id]
    ).fetchone()[0]

    if existing == 0:
        return jsonify({"error": "Author not found"}), 404

    # Build update query dynamically based on provided fields
    update_fields = []
    params = []

    allowed_fields = ['name', 'paper_dois', 'h_index', 'works_count', 'cited_by_count']

    for field in allowed_fields:
        if field in data:
            update_fields.append(f'{field} = ?')
            params.append(data[field])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(author_id)
    query = f"UPDATE authors SET {', '.join(update_fields)} WHERE author_id = ?"

    db.execute(query, params)

    return jsonify({"status": "updated", "author_id": author_id})


@authors_bp.route("/api/authors/<path:author_id>", methods=["DELETE"])
def delete_author(author_id):
    """Remove author from database."""
    db = get_db()

    # Hard delete author
    result = db.execute(
        "DELETE FROM authors WHERE author_id = ?",
        [author_id]
    )

    return jsonify({"status": "deleted", "author_id": author_id})


@authors_bp.route("/api/authors/generate", methods=["POST"])
def generate_author():
    """Auto-populate author info from ID. Input: author_id (OpenAlex/ORCID). Returns: name, papers, h-index."""
    # TODO: Implement external API integration (OpenAlex, ORCID)
    return jsonify({"error": "Not implemented yet"}), 501

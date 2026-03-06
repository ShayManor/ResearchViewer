from flask import Blueprint, request, jsonify
from src.database import get_db, df_to_json_serializable

papers = Blueprint("papers", __name__)


@papers.route("/api/papers", methods=["GET"])
def get_papers():
    """Get all papers with optional filters (subject, journal, date range, keyword). Supports pagination and sorting."""
    db = get_db()

    # Get query parameters
    subject = request.args.get('subject')
    journal = request.args.get('journal')
    keyword = request.args.get('keyword')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    sort_by = request.args.get('sort_by', 'update_date')
    sort_order = request.args.get('sort_order', 'DESC')

    # Build query
    query = "SELECT * FROM papers WHERE deleted = false OR deleted IS NULL"
    params = []

    if subject:
        query += " AND categories LIKE ?"
        params.append(f"%{subject}%")

    if journal:
        query += " AND \"journal-ref\" LIKE ?"
        params.append(f"%{journal}%")

    if keyword:
        query += " AND (title LIKE ? OR abstract LIKE ?)"
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")

    if start_date:
        query += " AND update_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND update_date <= ?"
        params.append(end_date)

    # Add sorting and pagination
    query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
    params.append(per_page)
    params.append((page - 1) * per_page)

    result = db.execute(query, params).fetchdf()

    return jsonify({
        "papers": df_to_json_serializable(result),
        "page": page,
        "per_page": per_page
    })


@papers.route("/api/count_papers", methods=["GET"])
def count_papers():
    """Get number of papers with optional filters (subject, journal, date range, keyword)."""
    db = get_db()

    # Get query parameters
    subject = request.args.get('subject')
    journal = request.args.get('journal')
    keyword = request.args.get('keyword')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Build query
    query = "SELECT COUNT(*) as count FROM papers WHERE deleted = false OR deleted IS NULL"
    params = []

    if subject:
        query += " AND categories LIKE ?"
        params.append(f"%{subject}%")

    if journal:
        query += " AND \"journal-ref\" LIKE ?"
        params.append(f"%{journal}%")

    if keyword:
        query += " AND (title LIKE ? OR abstract LIKE ?)"
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")

    if start_date:
        query += " AND update_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND update_date <= ?"
        params.append(end_date)

    result = db.execute(query, params).fetchone()

    return jsonify({"count": result[0]})


@papers.route("/api/papers/<path:doi>", methods=["GET"])
def get_paper(doi):
    """Get single paper by DOI. Returns title, abstract, authors, citations, keywords, journal, subject, submission time."""
    db = get_db()

    result = db.execute(
        "SELECT * FROM papers WHERE lower(doi) = lower(?) AND (deleted = false OR deleted IS NULL)",
        [doi]
    ).fetchdf()

    if result.empty:
        return jsonify({"error": "Paper not found"}), 404

    paper = df_to_json_serializable(result)[0]
    return jsonify(paper)


@papers.route("/api/papers", methods=["POST"])
def add_paper():
    """Add new paper. Input: title, doi, authors, citations, keywords, journal, subject, submission_time."""
    db = get_db()
    data = request.get_json()

    # Validate required fields
    if not data.get('doi'):
        return jsonify({"error": "DOI is required"}), 400

    if not data.get('title'):
        return jsonify({"error": "Title is required"}), 400

    # Check if paper already exists
    existing = db.execute(
        "SELECT COUNT(*) FROM papers WHERE lower(doi) = lower(?)",
        [data['doi']]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"error": "Paper with this DOI already exists"}), 409

    # Insert paper
    db.execute("""
        INSERT INTO papers (
            doi, title, abstract, authors, categories,
            "journal-ref", citations, author_ids, update_date, deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, false)
    """, [
        data.get('doi'),
        data.get('title'),
        data.get('abstract'),
        data.get('authors'),
        data.get('subject') or data.get('categories'),
        data.get('journal'),
        data.get('citations', []),
        data.get('author_ids', []),
        data.get('submission_time') or data.get('update_date')
    ])

    return jsonify({"status": "created", "doi": data['doi']}), 201


@papers.route("/api/papers/<path:doi>", methods=["PUT"])
def update_paper(doi):
    """Update existing paper by DOI. Input: fields to update."""
    db = get_db()
    data = request.get_json()

    # Check if paper exists
    existing = db.execute(
        "SELECT COUNT(*) FROM papers WHERE lower(doi) = lower(?)",
        [doi]
    ).fetchone()[0]

    if existing == 0:
        return jsonify({"error": "Paper not found"}), 404

    # Build update query dynamically based on provided fields
    update_fields = []
    params = []

    field_mapping = {
        'title': 'title',
        'abstract': 'abstract',
        'authors': 'authors',
        'subject': 'categories',
        'categories': 'categories',
        'journal': 'journal-ref',
        'citations': 'citations',
        'author_ids': 'author_ids'
    }

    for key, db_field in field_mapping.items():
        if key in data:
            update_fields.append(f'"{db_field}" = ?' if '-' in db_field else f'{db_field} = ?')
            params.append(data[key])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(doi)
    query = f"UPDATE papers SET {', '.join(update_fields)} WHERE lower(doi) = lower(?)"

    db.execute(query, params)

    return jsonify({"status": "updated", "doi": doi})


@papers.route("/api/papers/<path:doi>", methods=["DELETE"])
def delete_paper(doi):
    """Remove paper from database."""
    db = get_db()

    # Soft delete by setting deleted flag
    result = db.execute(
        "UPDATE papers SET deleted = true WHERE lower(doi) = lower(?)",
        [doi]
    )

    if result.fetchone() is None:
        return jsonify({"error": "Paper not found"}), 404

    return jsonify({"status": "deleted", "doi": doi})


@papers.route("/api/papers/generate", methods=["POST"])
def generate_paper():
    """Auto-populate paper info from DOI. Input: doi. Returns: title, authors, citations, keywords, subject."""
    # TODO: Implement external API integration (e.g., CrossRef, OpenAlex)
    return jsonify({"error": "Not implemented yet"}), 501


@papers.route("/api/papers/<path:doi>/citations", methods=["GET"])
def get_paper_citations(doi):
    """Get all papers that cite this paper."""
    db = get_db()

    # Find papers where this DOI is in their citations array
    result = db.execute("""
        SELECT * FROM papers
        WHERE list_contains(citations, ?)
        AND (deleted = false OR deleted IS NULL)
    """, [doi]).fetchdf()

    return jsonify({
        "citing_papers": df_to_json_serializable(result),
        "count": len(result)
    })


@papers.route("/api/papers/<path:doi>/references", methods=["GET"])
def get_paper_references(doi):
    """Get all papers this paper cites."""
    db = get_db()

    # Get the paper's citations array
    paper = db.execute(
        "SELECT citations FROM papers WHERE lower(doi) = lower(?)",
        [doi]
    ).fetchone()

    if not paper or not paper[0]:
        return jsonify({"references": [], "count": 0})

    citations = paper[0]

    # Get papers with DOIs in the citations list
    placeholders = ','.join(['?'] * len(citations))
    result = db.execute(f"""
        SELECT * FROM papers
        WHERE lower(doi) IN ({placeholders})
        AND (deleted = false OR deleted IS NULL)
    """, [c.lower() for c in citations]).fetchdf()

    return jsonify({
        "references": df_to_json_serializable(result),
        "count": len(result)
    })

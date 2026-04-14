import re

from flask import Blueprint, request, jsonify
from src.database import get_data_db as get_db, df_to_json_serializable
from src.sql_safety import (
    InvalidParameter,
    escape_like,
    safe_int,
    safe_sort_field,
    safe_sort_order,
)

papers_bp = Blueprint("papers", __name__)

# ISO date YYYY-MM-DD. We accept nothing else for date filters.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@papers_bp.route("/api/papers", methods=["GET"])
def get_papers():
    """Get all papers with optional filters. Supports pagination and sorting.

    All user input is sanitized before reaching SQL:
      * Free-text filters (keyword, author, subject) are bound as `?`
        parameters AND have LIKE wildcards escaped via `escape_like`.
      * Numeric filters go through `safe_int` (parsed + range-clamped).
      * Dates are regex-checked for ISO format before being bound.
      * `sort_by` / `sort_order` are matched against fixed allowlists
        before being interpolated into the ORDER BY clause.
    """
    db = get_db()

    try:
        page = safe_int(request.args.get('page'), default=1, minimum=1)
        per_page = safe_int(
            request.args.get('per_page'), default=20, minimum=1, maximum=100
        )
        min_citations = request.args.get('min_citations')
        max_citations = request.args.get('max_citations')
        if min_citations is not None:
            min_citations = safe_int(min_citations, default=0, minimum=0)
        if max_citations is not None:
            max_citations = safe_int(max_citations, default=0, minimum=0)
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400

    keyword = request.args.get('keyword')
    subject = request.args.get('subject')
    author = request.args.get('author')
    domain = request.args.get('domain')
    topic = request.args.get('topic')
    microtopic_id = request.args.get('microtopic_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    for label, value in (("start_date", start_date), ("end_date", end_date)):
        if value is not None and not _ISO_DATE_RE.match(value):
            return jsonify({"error": f"{label} must be YYYY-MM-DD"}), 400

    sort_by = safe_sort_field(
        request.args.get('sort_by'),
        allowed=('citation_count', 'update_date', 'title'),
        default='citation_count',
    )
    sort_order = safe_sort_order(request.args.get('sort_order'))

    # Build base query
    if microtopic_id:
        # Join with paper_microtopics for filtering by microtopic
        base_query = """
            SELECT DISTINCT p.* FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
        """
        count_query = """
            SELECT COUNT(DISTINCT p.id) FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
        """
        params = [microtopic_id]
    else:
        base_query = "SELECT * FROM papers WHERE (deleted = false OR deleted IS NULL)"
        count_query = "SELECT COUNT(*) FROM papers WHERE (deleted = false OR deleted IS NULL)"
        params = []

    # Add filters. Every value is bound as a `?` parameter; LIKE patterns
    # are escaped so user input cannot inject wildcards.
    if keyword:
        kw = f"%{escape_like(keyword)}%"
        filter_clause = (
            " AND (title ILIKE ? ESCAPE '\\'"
            " OR abstract ILIKE ? ESCAPE '\\'"
            " OR authors ILIKE ? ESCAPE '\\')"
        )
        base_query += filter_clause
        count_query += filter_clause
        params.extend([kw, kw, kw])

    if subject:
        filter_clause = " AND categories LIKE ? ESCAPE '\\'"
        base_query += filter_clause
        count_query += filter_clause
        params.append(f"%{escape_like(subject)}%")

    if author:
        filter_clause = " AND authors ILIKE ? ESCAPE '\\'"
        base_query += filter_clause
        count_query += filter_clause
        params.append(f"%{escape_like(author)}%")

    if domain:
        filter_clause = " AND primary_domain_name = ?"
        base_query += filter_clause
        count_query += filter_clause
        params.append(domain)

    if topic:
        filter_clause = " AND primary_topic_name = ?"
        base_query += filter_clause
        count_query += filter_clause
        params.append(topic)

    if start_date:
        filter_clause = " AND update_date >= ?"
        base_query += filter_clause
        count_query += filter_clause
        params.append(start_date)

    if end_date:
        filter_clause = " AND update_date <= ?"
        base_query += filter_clause
        count_query += filter_clause
        params.append(end_date)

    if min_citations is not None:
        filter_clause = " AND citation_count >= ?"
        base_query += filter_clause
        count_query += filter_clause
        params.append(min_citations)

    if max_citations is not None:
        filter_clause = " AND citation_count <= ?"
        base_query += filter_clause
        count_query += filter_clause
        params.append(max_citations)

    # Get total count (use a copy of params for count query)
    count_params = params.copy()
    total = db.execute(count_query, count_params).fetchone()[0]

    # Add sorting and pagination to main query
    query = base_query + f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
    params.append(per_page)
    params.append((page - 1) * per_page)

    result = db.execute(query, params).fetchdf()

    return jsonify({
        "papers": df_to_json_serializable(result),
        "page": page,
        "per_page": per_page,
        "total": total
    })


@papers_bp.route("/api/count_papers", methods=["GET"])
def count_papers():
    """Get number of papers with optional filters."""
    db = get_db()

    keyword = request.args.get('keyword')
    subject = request.args.get('subject')
    author = request.args.get('author')
    microtopic_id = request.args.get('microtopic_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    for label, value in (("start_date", start_date), ("end_date", end_date)):
        if value is not None and not _ISO_DATE_RE.match(value):
            return jsonify({"error": f"{label} must be YYYY-MM-DD"}), 400

    try:
        min_citations = request.args.get('min_citations')
        max_citations = request.args.get('max_citations')
        if min_citations is not None:
            min_citations = safe_int(min_citations, default=0, minimum=0)
        if max_citations is not None:
            max_citations = safe_int(max_citations, default=0, minimum=0)
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400

    if microtopic_id:
        query = """
            SELECT COUNT(DISTINCT p.id) FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
        """
        params = [microtopic_id]
    else:
        query = "SELECT COUNT(*) FROM papers WHERE deleted = false OR deleted IS NULL"
        params = []

    if keyword:
        kw = f"%{escape_like(keyword)}%"
        query += (
            " AND (title ILIKE ? ESCAPE '\\'"
            " OR abstract ILIKE ? ESCAPE '\\'"
            " OR authors ILIKE ? ESCAPE '\\')"
        )
        params.extend([kw, kw, kw])

    if subject:
        query += " AND categories LIKE ? ESCAPE '\\'"
        params.append(f"%{escape_like(subject)}%")

    if author:
        query += " AND authors ILIKE ? ESCAPE '\\'"
        params.append(f"%{escape_like(author)}%")

    if start_date:
        query += " AND update_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND update_date <= ?"
        params.append(end_date)

    if min_citations is not None:
        query += " AND citation_count >= ?"
        params.append(min_citations)

    if max_citations is not None:
        query += " AND citation_count <= ?"
        params.append(max_citations)

    result = db.execute(query, params).fetchone()

    return jsonify({"count": result[0]})


@papers_bp.route("/api/papers/<path:paper_id>", methods=["GET"])
def get_paper(paper_id):
    """Get single paper by arXiv ID or DOI. Returns full paper details including microtopics."""
    db = get_db()

    # Get paper details (search by both id and doi to handle both formats)
    result = db.execute(
        "SELECT * FROM papers WHERE (id = ? OR lower(doi) = lower(?)) AND (deleted = false OR deleted IS NULL)",
        [paper_id, paper_id]
    ).fetchdf()

    if result.empty:
        return jsonify({"error": "Paper not found"}), 404

    paper = df_to_json_serializable(result)[0]

    # Get microtopics for this paper
    microtopics_result = db.execute("""
        SELECT
            m.microtopic_id,
            m.label,
            pm.score,
            pm.is_primary
        FROM paper_microtopics pm
        INNER JOIN microtopics m ON pm.microtopic_id = m.microtopic_id
        WHERE pm.paper_id = ?
        ORDER BY pm.score DESC
    """, [paper_id]).fetchdf()

    if not microtopics_result.empty:
        paper['microtopics'] = df_to_json_serializable(microtopics_result)
    else:
        paper['microtopics'] = []

    return jsonify(paper)


@papers_bp.route("/api/papers", methods=["POST"])
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


@papers_bp.route("/api/papers/<path:doi>", methods=["PUT"])
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


@papers_bp.route("/api/papers/<path:doi>", methods=["DELETE"])
def delete_paper(doi):
    """Remove paper from database."""
    db = get_db()

    existing = db.execute(
        "SELECT COUNT(*) FROM papers WHERE lower(doi) = lower(?) AND (deleted = false OR deleted IS NULL)",
        [doi]
    ).fetchone()[0]

    if existing == 0:
        return jsonify({"error": "Paper not found"}), 404

    db.execute(
        "UPDATE papers SET deleted = true WHERE lower(doi) = lower(?)",
        [doi]
    )

    return jsonify({"status": "deleted", "doi": doi})


@papers_bp.route("/api/papers/generate", methods=["POST"])
def generate_paper():
    """Auto-populate paper info from DOI. Input: doi. Returns: title, authors, citations, keywords, subject."""
    # TODO: Implement external API integration (e.g., CrossRef, OpenAlex)
    return jsonify({"error": "Not implemented yet"}), 501


@papers_bp.route("/api/papers/<path:paper_id>/citations", methods=["GET"])
def get_paper_citations(paper_id):
    """Get all papers that cite this paper. Papers whose citations array contains this ID."""
    db = get_db()

    try:
        page = safe_int(request.args.get('page'), default=1, minimum=1)
        per_page = safe_int(
            request.args.get('per_page'), default=20, minimum=1, maximum=100
        )
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400

    sort_by = safe_sort_field(
        request.args.get('sort_by'),
        allowed=('citation_count', 'update_date', 'title'),
        default='citation_count',
    )
    sort_order = safe_sort_order(request.args.get('sort_order'))

    count = db.execute("""
        SELECT COUNT(*) FROM papers
        WHERE list_contains(citations, ?)
        AND (deleted = false OR deleted IS NULL)
    """, [paper_id]).fetchone()[0]

    result = db.execute(f"""
        SELECT * FROM papers
        WHERE list_contains(citations, ?)
        AND (deleted = false OR deleted IS NULL)
        ORDER BY {sort_by} {sort_order}
        LIMIT ? OFFSET ?
    """, [paper_id, per_page, (page - 1) * per_page]).fetchdf()

    return jsonify({
        "citing_papers": df_to_json_serializable(result),
        "count": count,
        "page": page,
        "per_page": per_page
    })


@papers_bp.route("/api/papers/<path:paper_id>/references", methods=["GET"])
def get_paper_references(paper_id):
    """Get all papers this paper cites. Look up each ID in the paper's citations array."""
    db = get_db()

    try:
        page = safe_int(request.args.get('page'), default=1, minimum=1)
        per_page = safe_int(
            request.args.get('per_page'), default=20, minimum=1, maximum=100
        )
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400

    paper = db.execute(
        "SELECT citations FROM papers WHERE id = ?",
        [paper_id]
    ).fetchone()

    if not paper or paper[0] is None or len(paper[0]) == 0:
        return jsonify({"references": [], "count": 0, "page": page, "per_page": per_page})

    citations = list(paper[0])
    placeholders = ','.join(['?'] * len(citations))

    count = db.execute(f"""
        SELECT COUNT(*) FROM papers
        WHERE id IN ({placeholders})
        AND (deleted = false OR deleted IS NULL)
    """, citations).fetchone()[0]

    result = db.execute(f"""
        SELECT * FROM papers
        WHERE id IN ({placeholders})
        AND (deleted = false OR deleted IS NULL)
        LIMIT ? OFFSET ?
    """, citations + [per_page, (page - 1) * per_page]).fetchdf()

    return jsonify({
        "references": df_to_json_serializable(result),
        "count": count,
        "page": page,
        "per_page": per_page
    })

from flask import Blueprint, request, jsonify
from src.database import get_db, df_to_json_serializable

analytics = Blueprint("analytics", __name__)


@analytics.route("/api/analytics/papers/over-time", methods=["GET"])
def papers_over_time():
    """Get paper counts over time. Query params: group_by (year/month), subject (optional)."""
    db = get_db()

    group_by = request.args.get('group_by', 'year')
    subject = request.args.get('subject')

    # Determine date grouping
    if group_by == 'month':
        date_trunc = "strftime(update_date, '%Y-%m')"
    else:  # year
        date_trunc = "strftime(update_date, '%Y')"

    # Build query
    query = f"""
        SELECT {date_trunc} as period, COUNT(*) as count
        FROM papers
        WHERE update_date IS NOT NULL
        AND (deleted = false OR deleted IS NULL)
    """
    params = []

    if subject:
        query += " AND categories LIKE ?"
        params.append(f"%{subject}%")

    query += " GROUP BY period ORDER BY period"

    result = db.execute(query, params).fetchdf()

    return jsonify({
        "data": df_to_json_serializable(result),
        "group_by": group_by
    })


@analytics.route("/api/analytics/citations/distribution", methods=["GET"])
def citations_distribution():
    """Get citation count distribution across papers."""
    db = get_db()

    result = db.execute("""
        SELECT
            CASE
                WHEN citation_count = 0 THEN '0'
                WHEN citation_count BETWEEN 1 AND 5 THEN '1-5'
                WHEN citation_count BETWEEN 6 AND 10 THEN '6-10'
                WHEN citation_count BETWEEN 11 AND 25 THEN '11-25'
                WHEN citation_count BETWEEN 26 AND 50 THEN '26-50'
                WHEN citation_count BETWEEN 51 AND 100 THEN '51-100'
                WHEN citation_count BETWEEN 101 AND 500 THEN '101-500'
                ELSE '500+'
            END as citation_range,
            COUNT(*) as paper_count
        FROM papers
        WHERE deleted = false OR deleted IS NULL
        GROUP BY citation_range
        ORDER BY MIN(citation_count)
    """).fetchdf()

    return jsonify({"distribution": df_to_json_serializable(result)})


@analytics.route("/api/analytics/subjects", methods=["GET"])
def subjects_breakdown():
    """Get paper counts by subject."""
    db = get_db()

    limit = int(request.args.get('limit', 20))

    # Extract primary category (first in the list)
    result = db.execute("""
        SELECT
            SPLIT_PART(categories, ' ', 1) as subject,
            COUNT(*) as paper_count
        FROM papers
        WHERE categories IS NOT NULL
        AND (deleted = false OR deleted IS NULL)
        GROUP BY subject
        ORDER BY paper_count DESC
        LIMIT ?
    """, [limit]).fetchdf()

    return jsonify({"subjects": df_to_json_serializable(result)})


@analytics.route("/api/analytics/authors/top", methods=["GET"])
def top_authors():
    """Get top authors by h-index or paper count."""
    db = get_db()

    sort_by = request.args.get('sort_by', 'h_index')
    limit = int(request.args.get('limit', 50))

    # Validate sort_by
    allowed_sorts = ['h_index', 'works_count', 'cited_by_count']
    if sort_by not in allowed_sorts:
        sort_by = 'h_index'

    result = db.execute(f"""
        SELECT author_id, name, h_index, works_count, cited_by_count
        FROM authors
        WHERE {sort_by} IS NOT NULL
        ORDER BY {sort_by} DESC
        LIMIT ?
    """, [limit]).fetchdf()

    return jsonify({
        "top_authors": df_to_json_serializable(result),
        "sorted_by": sort_by
    })


@analytics.route("/api/analytics/graph", methods=["GET"])
def citation_graph():
    """Get citation/author graph data for visualization. Query params: subject (optional), limit."""
    db = get_db()

    subject = request.args.get('subject')
    limit = int(request.args.get('limit', 100))

    # Build query for papers
    query = """
        SELECT doi, title, categories, citation_count, citations
        FROM papers
        WHERE (deleted = false OR deleted IS NULL)
        AND citations IS NOT NULL
        AND array_length(citations) > 0
    """
    params = []

    if subject:
        query += " AND categories LIKE ?"
        params.append(f"%{subject}%")

    query += " ORDER BY citation_count DESC LIMIT ?"
    params.append(limit)

    papers_result = db.execute(query, params).fetchdf()

    # Build nodes and edges for graph
    nodes = []
    edges = []
    node_ids = set()

    for _, paper in papers_result.iterrows():
        doi = paper['doi']
        if doi not in node_ids:
            nodes.append({
                'id': doi,
                'label': paper['title'][:50] + '...' if len(paper['title']) > 50 else paper['title'],
                'category': paper['categories'].split()[0] if paper['categories'] else 'unknown',
                'citation_count': int(paper['citation_count']) if paper['citation_count'] else 0
            })
            node_ids.add(doi)

        # Add edges for citations
        if paper['citations'] is not None and len(paper['citations']) > 0:
            for cited_doi in paper['citations']:
                if cited_doi:
                    edges.append({
                        'source': doi,
                        'target': cited_doi,
                        'type': 'citation'
                    })
                    # Add target node if not already present
                    if cited_doi not in node_ids:
                        nodes.append({
                            'id': cited_doi,
                            'label': cited_doi[:30],
                            'category': 'unknown',
                            'citation_count': 0
                        })
                        node_ids.add(cited_doi)

    return jsonify({
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges)
    })

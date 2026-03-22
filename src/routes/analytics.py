from flask import Blueprint, request, jsonify
from src.database import get_data_db as get_db, df_to_json_serializable
from src.cache import cache

analytics = Blueprint("analytics", __name__)


@analytics.route("/api/analytics/papers/over-time", methods=["GET"])
def papers_over_time():
    """Get paper counts and citation totals over time."""
    db = get_db()

    group_by = request.args.get('group_by', 'year')
    subject = request.args.get('subject')
    microtopic_id = request.args.get('microtopic_id')

    # Determine date grouping
    if group_by == 'month':
        date_trunc = "strftime(update_date, '%Y-%m')"
    else:  # year
        date_trunc = "strftime(update_date, '%Y')"

    # Build query based on filters
    if microtopic_id:
        query = f"""
            SELECT
                {date_trunc} as period,
                COUNT(*) as count,
                SUM(p.citation_count) as total_citations
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND p.update_date IS NOT NULL
            AND (p.deleted = false OR p.deleted IS NULL)
        """
        params = [microtopic_id]
    else:
        query = f"""
            SELECT
                {date_trunc} as period,
                COUNT(*) as count,
                SUM(citation_count) as total_citations
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
    """Get citation count distribution across papers with optional filters."""
    db = get_db()

    subject = request.args.get('subject')
    microtopic_id = request.args.get('microtopic_id')

    # Build query with filters
    if microtopic_id:
        base_query = """
            SELECT p.citation_count
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
        """
        params = [microtopic_id]
    else:
        base_query = """
            SELECT citation_count
            FROM papers
            WHERE deleted = false OR deleted IS NULL
        """
        params = []

    if subject:
        base_query += " AND categories LIKE ?"
        params.append(f"%{subject}%")

    query = f"""
        WITH paper_citations AS ({base_query})
        SELECT
            CASE
                WHEN citation_count = 0 THEN '0'
                WHEN citation_count BETWEEN 1 AND 5 THEN '1-5'
                WHEN citation_count BETWEEN 6 AND 10 THEN '6-10'
                WHEN citation_count BETWEEN 11 AND 25 THEN '11-25'
                WHEN citation_count BETWEEN 26 AND 50 THEN '26-50'
                WHEN citation_count BETWEEN 51 AND 100 THEN '51-100'
                WHEN citation_count BETWEEN 101 AND 500 THEN '101-500'
                WHEN citation_count BETWEEN 501 AND 1000 THEN '501-1000'
                WHEN citation_count BETWEEN 1001 AND 5000 THEN '1001-5000'
                WHEN citation_count BETWEEN 5001 AND 10000 THEN '5001-10000'
                ELSE '10000+'
            END as citation_range,
            COUNT(*) as paper_count
        FROM paper_citations
        GROUP BY citation_range
        ORDER BY MIN(citation_count)
    """

    result = db.execute(query, params).fetchdf()

    return jsonify({"distribution": df_to_json_serializable(result)})


@analytics.route("/api/analytics/subjects", methods=["GET"])
def subjects_breakdown():
    """Get paper counts by subject with average citations."""
    db = get_db()

    limit = int(request.args.get('limit', 20))

    # Extract primary category (first in the list) and calculate avg citations
    result = db.execute("""
        SELECT
            primary_topic_name as subject,
            COUNT(*) as paper_count,
            ROUND(AVG(citation_count), 0) as avg_citations
        FROM papers
        WHERE primary_topic_name IS NOT NULL
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
    subject = request.args.get('subject')
    limit = min(int(request.args.get('limit', 50)), 200)

    # Validate sort_by
    allowed_sorts = ['h_index', 'works_count', 'cited_by_count']
    if sort_by not in allowed_sorts:
        sort_by = 'h_index'

    # If subject filter, join with papers
    if subject:
        result = db.execute(f"""
            SELECT DISTINCT
                a.author_id, a.name, a.h_index, a.works_count, a.cited_by_count
            FROM authors a
            INNER JOIN papers p ON p.id = ANY(a.paper_dois)
            WHERE p.categories LIKE ?
            AND a.{sort_by} IS NOT NULL
            AND (p.deleted = false OR p.deleted IS NULL)
            ORDER BY a.{sort_by} DESC
            LIMIT ?
        """, [f"%{subject}%", limit]).fetchdf()
    else:
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


@analytics.route("/api/analytics/velocity", methods=["GET"])
def submission_velocity():
    """Paper submission velocity over recent time periods."""
    db = get_db()

    period = request.args.get('period', 'week')
    subject = request.args.get('subject')
    lookback = int(request.args.get('lookback', 12))

    import datetime

    # Calculate period dates
    today = datetime.date.today()
    periods = []

    if period == 'week':
        for i in range(lookback):
            period_end = today - datetime.timedelta(weeks=i)
            period_start = period_end - datetime.timedelta(days=7)
            periods.append((period_start, period_end))
    else:  # month
        for i in range(lookback):
            period_end = today - datetime.timedelta(days=30*i)
            period_start = period_end - datetime.timedelta(days=30)
            periods.append((period_start, period_end))

    # Query each period
    velocity_data = []
    for period_start, period_end in reversed(periods):
        query = """
            SELECT COUNT(*) as count
            FROM papers
            WHERE update_date BETWEEN ? AND ?
            AND (deleted = false OR deleted IS NULL)
        """
        params = [period_start.isoformat(), period_end.isoformat()]

        if subject:
            query += " AND categories LIKE ?"
            params.append(f"%{subject}%")

        count = db.execute(query, params).fetchone()[0]

        velocity_data.append({
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'count': count
        })

    # Calculate statistics
    counts = [v['count'] for v in velocity_data]
    avg = sum(counts) / len(counts) if counts else 0
    latest = counts[-1] if counts else 0
    delta = latest - avg
    delta_pct = (delta / avg * 100) if avg > 0 else 0

    return jsonify({
        "velocity": velocity_data,
        "period": period,
        "avg": round(avg, 0),
        "latest": latest,
        "delta": round(delta, 0),
        "delta_pct": round(delta_pct, 1)
    })


@analytics.route("/api/analytics/hot-papers", methods=["GET"])
@cache.cached(timeout=300, query_string=True)
def hot_papers():
    """Recently published papers with high citation growth."""
    db = get_db()

    subject = request.args.get('subject')
    since = request.args.get('since')
    sort_by = request.args.get('sort_by', 'citation_count')
    limit = int(request.args.get('limit', 10))
    user_id = request.args.get('user_id')  # Optional: filter out user's read papers

    # Default to 2 years ago
    if not since:
        import datetime
        two_years_ago = datetime.date.today() - datetime.timedelta(days=730)
        since = two_years_ago.isoformat()

    # Validate sort field
    allowed_sorts = ['citation_count', 'update_date']
    if sort_by not in allowed_sorts:
        sort_by = 'citation_count'

    # Build query
    query = f"""
        SELECT id, title, citation_count, update_date, categories, authors
        FROM papers
        WHERE update_date >= ?
        AND (deleted = false OR deleted IS NULL)
    """
    params = [since]

    # Exclude papers the user has already read
    if user_id:
        query += """
            AND id NOT IN (
                SELECT paper_id FROM user_read_history WHERE user_id = ?
            )
        """
        params.append(int(user_id))

    if subject:
        query += " AND categories LIKE ?"
        params.append(f"%{subject}%")

    query += f" ORDER BY {sort_by} DESC LIMIT ?"
    params.append(limit)

    result = db.execute(query, params).fetchdf()

    return jsonify({
        "papers": df_to_json_serializable(result)
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

@analytics.route("/api/analytics/domains", methods=["GET"])
def domains():
    """Get paper counts grouped by primary_domain_name."""
    db = get_db()
    limit = int(request.args.get('limit', 100))

    result = db.execute("""
        SELECT
            primary_domain_name as domain,
            COUNT(*) as paper_count,
            ROUND(AVG(citation_count), 0) as avg_citations,
            SUM(citation_count) as total_citations
        FROM papers
        WHERE primary_domain_name IS NOT NULL
        AND primary_domain_name != ''
        AND (deleted = false OR deleted IS NULL)
        GROUP BY primary_domain_name
        ORDER BY paper_count DESC
        LIMIT ?
    """, [limit]).fetchdf()

    return jsonify({"domains": df_to_json_serializable(result)})


@analytics.route("/api/analytics/topics", methods=["GET"])
def topics_in_domain():
    """Get paper counts grouped by primary_topic_name within a domain."""
    db = get_db()
    domain = request.args.get('domain')
    limit = int(request.args.get('limit', 100))

    if not domain:
        return jsonify({"error": "domain query param is required"}), 400

    result = db.execute("""
        SELECT
            primary_topic_name as topic,
            COUNT(*) as paper_count,
            ROUND(AVG(citation_count), 0) as avg_citations,
            SUM(citation_count) as total_citations
        FROM papers
        WHERE primary_domain_name = ?
        AND primary_topic_name IS NOT NULL
        AND primary_topic_name != ''
        AND (deleted = false OR deleted IS NULL)
        GROUP BY primary_topic_name
        ORDER BY paper_count DESC
        LIMIT ?
    """, [domain, limit]).fetchdf()

    return jsonify({"topics": df_to_json_serializable(result)})

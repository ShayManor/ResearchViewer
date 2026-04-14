import json
import re

from flask import Blueprint, request, jsonify
from src.cache import cache
from src.database import get_data_db as get_db, df_to_json_serializable
from src.sql_safety import (
    InvalidParameter,
    safe_int,
    safe_sort_field,
    safe_sort_order,
)

microtopics_bp = Blueprint("microtopics", __name__)

# Microtopic IDs are short alphanumeric tokens. Anything else is rejected
# outright so we never even bind a hostile value to the query.
_MICROTOPIC_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


@microtopics_bp.route("/api/microtopics", methods=["GET"])
@cache.cached(timeout=300, query_string=True)
def get_microtopics():
    """List microtopics with filtering."""
    db = get_db()

    # Get query parameters
    bucket_value = request.args.get('bucket_value')
    min_size = request.args.get('min_size')
    search = request.args.get('search')
    sort_by = request.args.get('sort_by', 'size')
    sort_order = request.args.get('sort_order', 'DESC')
    limit = min(int(request.args.get('limit', 50)), 200)

    # Validate sort field
    allowed_sorts = ['size', 'label', 'created_at']
    if sort_by not in allowed_sorts:
        sort_by = 'size'

    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    query = "SELECT microtopic_id, label, bucket_value, size FROM microtopics WHERE 1=1"
    params = []

    if bucket_value:
        query += " AND bucket_value = ?"
        params.append(bucket_value)

    if min_size:
        query += " AND size >= ?"
        params.append(int(min_size))

    if search:
        query += " AND label ILIKE ?"
        params.append(f"%{search}%")

    query += f" ORDER BY {sort_by} {sort_order} LIMIT ?"
    params.append(limit)

    result = db.execute(query, params).fetchdf()

    if result.empty:
        microtopics = []
    else:
        microtopics = result.to_dict('records')
        # Convert size to int (DuckDB returns numpy types)
        for topic in microtopics:
            topic['size'] = int(topic['size'])

    return jsonify({
        "microtopics": microtopics,
        "count": len(microtopics)
    })


@microtopics_bp.route("/api/microtopics/<microtopic_id>", methods=["GET"])
@cache.cached(timeout=300, query_string=True)
def get_microtopic_detail(microtopic_id):
    """Full detail for a single microtopic including aggregated statistics."""
    db = get_db()

    # Get basic microtopic info
    result = db.execute(
        "SELECT * FROM microtopics WHERE microtopic_id = ?",
        [microtopic_id]
    ).fetchone()

    if not result:
        return jsonify({"error": "Microtopic not found"}), 404

    # Build base response
    microtopic = {
        'microtopic_id': result[0],
        'bucket_column': result[1],
        'bucket_value': result[2],
        'cluster_id': result[3],
        'label': result[4],
        'size': result[5],
        'top_terms': json.loads(result[6]) if result[6] else [],
        'representative_titles': json.loads(result[7]) if result[7] else []
    }

    # Calculate statistics using SQL aggregations (much faster than Python)
    import datetime
    current_year = datetime.datetime.now().year

    stats = db.execute("""
        SELECT
            COUNT(DISTINCT p.id) as paper_count,
            COALESCE(SUM(p.citation_count), 0) as total_citations,
            COALESCE(AVG(p.citation_count), 0) as avg_citations,
            COALESCE(MEDIAN(p.citation_count), 0) as median_citations,
            COALESCE(MAX(p.citation_count), 0) as max_citations,
            MIN(CAST(strftime(p.update_date, '%Y') AS INTEGER)) as min_year,
            MAX(CAST(strftime(p.update_date, '%Y') AS INTEGER)) as max_year,
            SUM(CASE WHEN CAST(strftime(p.update_date, '%Y') AS INTEGER) >= ? THEN 1 ELSE 0 END) as recent_count
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND (p.deleted = false OR p.deleted IS NULL)
    """, [current_year - 2, microtopic_id]).fetchone()

    paper_count = int(stats[0])

    if paper_count > 0:
        total_citations = int(stats[1])
        avg_citations = float(stats[2])
        median_citations = float(stats[3])
        max_citations = int(stats[4])
        min_year = stats[5]
        max_year = stats[6]
        recent_count = stats[7]
        year_range = f"{min_year}-{max_year}"
        recent_growth_pct = (recent_count / paper_count) * 100

        # Get paper data for author parsing and grouping (only needed fields)
        papers = db.execute("""
            SELECT DISTINCT p.id, p.citation_count, p.authors, strftime(p.update_date, '%Y') as year
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
        """, [microtopic_id]).fetchdf()

        # Calculate unique authors (single pass)
        unique_authors = set()
        author_counts = {}
        for authors_str in papers['authors'].dropna():
            if authors_str:
                for author in str(authors_str).split(',')[:3]:
                    author = author.strip()
                    if author:
                        unique_authors.add(author)
                        if author not in author_counts:
                            author_counts[author] = {'count': 0, 'citations': 0}
                        author_counts[author]['count'] += 1

        microtopic['stats'] = {
            'total_citations': total_citations,
            'avg_citations': avg_citations,
            'median_citations': median_citations,
            'max_citations': max_citations,
            'paper_count': paper_count,
            'year_range': year_range,
            'recent_growth_pct': round(recent_growth_pct, 1),
            'unique_author_count': len(unique_authors)
        }

        # Papers by year
        papers_by_year = papers.groupby('year').agg({
            'id': 'count',
            'citation_count': 'sum'
        }).reset_index()
        papers_by_year.columns = ['year', 'count', 'total_citations']
        microtopic['papers_by_year'] = df_to_json_serializable(papers_by_year)

        # Citation distribution
        def citation_bucket(count):
            if count >= 100000:
                return '100k+'
            elif count >= 10000:
                return '10k-100k'
            elif count >= 1000:
                return '1k-10k'
            elif count >= 100:
                return '100-1k'
            elif count >= 10:
                return '10-100'
            else:
                return '0-10'

        papers['citation_bucket'] = papers['citation_count'].apply(citation_bucket)
        citation_dist = papers.groupby('citation_bucket').size().reset_index(name='count')
        microtopic['citation_distribution'] = df_to_json_serializable(citation_dist)

        # Top authors (already calculated above)
        top_authors = sorted(
            [{'name': name, 'paper_count': stats_dict['count'], 'total_citations': stats_dict['citations']}
             for name, stats_dict in author_counts.items()],
            key=lambda x: x['paper_count'],
            reverse=True
        )[:10]

        microtopic['top_authors'] = top_authors

        # Top papers (fetch directly from database)
        top_papers_result = db.execute("""
            SELECT DISTINCT p.id, p.title, p.citation_count, p.update_date, p.authors
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
            ORDER BY p.citation_count DESC
            LIMIT 10
        """, [microtopic_id]).fetchdf()
        microtopic['top_papers'] = df_to_json_serializable(top_papers_result)
    else:
        microtopic['stats'] = {
            'total_citations': 0,
            'avg_citations': 0,
            'median_citations': 0,
            'max_citations': 0,
            'paper_count': 0,
            'year_range': '',
            'recent_growth_pct': 0
        }
        microtopic['papers_by_year'] = []
        microtopic['citation_distribution'] = []
        microtopic['top_authors'] = []
        microtopic['top_papers'] = []

    return jsonify(microtopic)


@microtopics_bp.route("/api/microtopics/<microtopic_id>/papers", methods=["GET"])
@cache.cached(timeout=300, query_string=True)
def get_microtopic_papers(microtopic_id):
    """Papers belonging to a microtopic, paginated.

    Sanitization layers:
      * `microtopic_id` (URL segment) is regex-checked, then bound as `?`.
      * `page` / `per_page` go through `safe_int` with bounds.
      * `sort_by` / `sort_order` are matched against fixed allowlists; the
        ORDER BY clause is then assembled from constants only — no string
        from `request.args` is ever interpolated into the SQL.
    """
    if not _MICROTOPIC_ID_RE.match(microtopic_id or ""):
        return jsonify({"error": "invalid microtopic_id"}), 400

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
        allowed=('citation_count', 'update_date', 'score'),
        default='citation_count',
    )
    sort_order = safe_sort_order(request.args.get('sort_order'))

    # Map allowlisted sort_by -> a fixed, hand-written ORDER BY fragment.
    # Because the value comes from a literal dict (not request.args), there
    # is no path for user input to influence the SQL string here.
    _ORDER_CLAUSES = {
        'citation_count': 'p.citation_count',
        'update_date': 'p.update_date',
        'score': 'pm.score',
    }
    order_clause = f"{_ORDER_CLAUSES[sort_by]} {sort_order}"

    # Get total count (use DISTINCT to avoid counting duplicates)
    total = db.execute("""
        SELECT COUNT(DISTINCT p.id)
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND (p.deleted = false OR p.deleted IS NULL)
    """, [microtopic_id]).fetchone()[0]

    # Get paginated results (use subquery to ensure DISTINCT works with ORDER BY)
    result = db.execute(f"""
        SELECT DISTINCT
            p.id, p.title, p.citation_count, p.update_date, p.authors,
            pm.score, pm.is_primary
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND (p.deleted = false OR p.deleted IS NULL)
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """, [microtopic_id, per_page, (page - 1) * per_page]).fetchdf()

    return jsonify({
        "papers": df_to_json_serializable(result),
        "page": page,
        "per_page": per_page,
        "total": total
    })


@microtopics_bp.route("/api/microtopics/compare", methods=["GET"])
def compare_microtopics():
    """Compare two microtopics side by side."""
    db = get_db()

    topic_a_id = request.args.get('topic_a')
    topic_b_id = request.args.get('topic_b')

    if not topic_a_id or not topic_b_id:
        return jsonify({"error": "Both topic_a and topic_b are required"}), 400

    # Get both topics
    topic_a = get_topic_data(db, topic_a_id)
    topic_b = get_topic_data(db, topic_b_id)

    if not topic_a:
        return jsonify({"error": "topic_a not found"}), 404
    if not topic_b:
        return jsonify({"error": "topic_b not found"}), 404

    # Calculate overlap
    papers_a = set(db.execute("""
        SELECT paper_id FROM paper_microtopics WHERE microtopic_id = ?
    """, [topic_a_id]).fetchdf()['paper_id'].tolist())

    papers_b = set(db.execute("""
        SELECT paper_id FROM paper_microtopics WHERE microtopic_id = ?
    """, [topic_b_id]).fetchdf()['paper_id'].tolist())

    shared_papers = papers_a.intersection(papers_b)
    shared_paper_count = len(shared_papers)

    # Jaccard similarity
    union_size = len(papers_a.union(papers_b))
    jaccard_similarity = shared_paper_count / union_size if union_size > 0 else 0

    # Get shared paper details
    if shared_papers:
        placeholders = ','.join(['?'] * len(shared_papers))
        shared_paper_details = db.execute(f"""
            SELECT id, title, citation_count
            FROM papers
            WHERE id IN ({placeholders})
            ORDER BY citation_count DESC
            LIMIT 10
        """, list(shared_papers)).fetchdf()
        shared_papers_list = df_to_json_serializable(shared_paper_details)
    else:
        shared_papers_list = []

    # Calculate shared authors with improved parsing
    def parse_authors(authors_str):
        """Parse author string handling 'and' separator."""
        authors = set()
        if not authors_str:
            return authors

        # Replace ' and ' with ',' for consistent parsing
        authors_str = str(authors_str).replace(' and ', ', ')

        # Split by comma and clean up
        for author in authors_str.split(','):
            author = author.strip()
            # Remove common prefixes/suffixes
            author = author.replace('et al.', '').replace('et al', '').strip()
            if author and len(author) > 2:  # Ignore single letters/initials
                # Normalize to last name only for better matching
                # Take the last word which is typically the surname
                parts = author.split()
                if parts:
                    surname = parts[-1]
                    # Only add if it looks like a real name (not a number, not too short)
                    if surname.isalpha() and len(surname) > 2:
                        authors.add(surname.lower())
        return authors

    authors_a = set()
    authors_b = set()

    # Get authors from topic A (limit to 1000 papers for performance)
    authors_a_result = db.execute("""
        SELECT DISTINCT p.authors
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND p.authors IS NOT NULL
        AND (p.deleted = false OR p.deleted IS NULL)
        LIMIT 1000
    """, [topic_a_id]).fetchdf()

    for authors_str in authors_a_result['authors'].dropna():
        authors_a.update(parse_authors(authors_str))

    # Get authors from topic B (limit to 1000 papers for performance)
    authors_b_result = db.execute("""
        SELECT DISTINCT p.authors
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND p.authors IS NOT NULL
        AND (p.deleted = false OR p.deleted IS NULL)
        LIMIT 1000
    """, [topic_b_id]).fetchdf()

    for authors_str in authors_b_result['authors'].dropna():
        authors_b.update(parse_authors(authors_str))

    shared_author_count = len(authors_a.intersection(authors_b))

    overlap = {
        'shared_paper_count': shared_paper_count,
        'shared_author_count': shared_author_count,
        'cross_citation_count': 0,  # Kept at 0 as it's expensive to calculate
        'jaccard_similarity': round(jaccard_similarity, 3),
        'shared_papers': shared_papers_list
    }

    return jsonify({
        "topic_a": topic_a,
        "topic_b": topic_b,
        "overlap": overlap
    })


def get_topic_data(db, microtopic_id):
    """Helper to get topic data for comparison."""
    result = db.execute(
        "SELECT * FROM microtopics WHERE microtopic_id = ?",
        [microtopic_id]
    ).fetchone()

    if not result:
        return None

    # Get stats using SQL aggregations (optimized)
    stats = db.execute("""
        SELECT
            COUNT(DISTINCT p.id) as paper_count,
            COALESCE(SUM(p.citation_count), 0) as total_citations,
            COALESCE(AVG(p.citation_count), 0) as avg_citations,
            COALESCE(MEDIAN(p.citation_count), 0) as median_citations,
            COALESCE(MAX(p.citation_count), 0) as max_citations
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND (p.deleted = false OR p.deleted IS NULL)
    """, [microtopic_id]).fetchone()

    topic = {
        'microtopic_id': result[0],
        'label': result[4],
        'size': result[5]
    }

    paper_count = int(stats[0])
    if paper_count > 0:
        topic['stats'] = {
            'total_citations': int(stats[1]),
            'avg_citations': float(stats[2]),
            'median_citations': float(stats[3]),
            'max_citations': int(stats[4]),
            'paper_count': paper_count
        }

        # Top papers (optimized query)
        top_papers_result = db.execute("""
            SELECT DISTINCT p.id, p.title, p.citation_count
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
            ORDER BY p.citation_count DESC
            LIMIT 5
        """, [microtopic_id]).fetchdf()
        topic['top_papers'] = df_to_json_serializable(top_papers_result)

        # Papers by year (optimized query)
        papers_by_year = db.execute("""
            SELECT
                strftime(p.update_date, '%Y') as year,
                COUNT(*) as count
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
            GROUP BY year
            ORDER BY year
        """, [microtopic_id]).fetchdf()
        topic['papers_by_year'] = df_to_json_serializable(papers_by_year)
    else:
        topic['stats'] = {'total_citations': 0, 'avg_citations': 0, 'median_citations': 0, 'max_citations': 0, 'paper_count': 0}
        topic['top_papers'] = []
        topic['papers_by_year'] = []

    return topic


@microtopics_bp.route("/api/microtopics/graph", methods=["GET"])
@cache.cached(timeout=300, query_string=True)
def microtopics_graph():
    """Returns a graph of microtopics as nodes and their relationships as edges."""
    db = get_db()

    # Get query parameters
    bucket_value = request.args.get('bucket_value')
    min_size = int(request.args.get('min_size', 5))
    min_edge_weight = float(request.args.get('min_edge_weight', 0.01))
    limit = min(int(request.args.get('limit', 100)), 200)

    # Get microtopics
    query = "SELECT * FROM microtopics WHERE size >= ?"
    params = [min_size]

    if bucket_value:
        query += " AND bucket_value = ?"
        params.append(bucket_value)

    query += " ORDER BY size DESC LIMIT ?"
    params.append(limit)

    topics = db.execute(query, params).fetchdf()

    if topics.empty:
        return jsonify({
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0
        })

    topic_ids = topics['microtopic_id'].tolist()

    # OPTIMIZED: Batch query for all paper stats at once instead of N+1 queries
    placeholders = ','.join(['?'] * len(topic_ids))
    all_stats = db.execute(f"""
        SELECT
            pm.microtopic_id,
            COUNT(DISTINCT p.id) as paper_count,
            COALESCE(AVG(p.citation_count), 0) as avg_citations,
            COALESCE(SUM(p.citation_count), 0) as total_citations,
            MAX(p.title) as top_paper_title
        FROM paper_microtopics pm
        INNER JOIN papers p ON p.id = pm.paper_id
        WHERE pm.microtopic_id IN ({placeholders})
        AND (p.deleted = false OR p.deleted IS NULL)
        GROUP BY pm.microtopic_id
    """, topic_ids).fetchdf()

    # Create lookup dict for O(1) access
    stats_lookup = {row['microtopic_id']: row for _, row in all_stats.iterrows()}

    # Build nodes
    nodes = []
    for _, topic in topics.iterrows():
        topic_id = topic['microtopic_id']
        stats = stats_lookup.get(topic_id)

        node = {
            'id': topic_id,
            'label': topic['label'],
            'bucket_value': topic['bucket_value'],
            'size': int(topic['size']),
            'avg_citations': float(stats['avg_citations']) if stats is not None else 0,
            'total_citations': int(stats['total_citations']) if stats is not None else 0,
            'recent_growth_pct': 0,  # Simplified
            'top_paper_title': stats['top_paper_title'] if stats is not None else ''
        }
        nodes.append(node)

    # OPTIMIZED: Batch query for all paper-topic relationships at once
    all_paper_topics = db.execute(f"""
        SELECT microtopic_id, paper_id
        FROM paper_microtopics
        WHERE microtopic_id IN ({placeholders})
    """, topic_ids).fetchdf()

    # Group by topic for O(1) lookup
    topic_papers = {}
    for _, row in all_paper_topics.iterrows():
        topic_id = row['microtopic_id']
        if topic_id not in topic_papers:
            topic_papers[topic_id] = set()
        topic_papers[topic_id].add(row['paper_id'])

    # Calculate edges
    edges = []
    for i, topic_a in enumerate(topic_ids):
        for topic_b in topic_ids[i+1:]:
            papers_a = topic_papers.get(topic_a, set())
            papers_b = topic_papers.get(topic_b, set())

            if not papers_a or not papers_b:
                continue

            shared_papers = papers_a.intersection(papers_b)
            shared_count = len(shared_papers)

            if shared_count > 0:
                # Jaccard similarity
                jaccard = shared_count / len(papers_a.union(papers_b))

                # Edge weight formula (simplified - no cross-citations for performance)
                weight = jaccard * 0.3 + (shared_count / max(len(papers_a), len(papers_b))) * 0.7

                if weight >= min_edge_weight:
                    edges.append({
                        'source': topic_a,
                        'target': topic_b,
                        'weight': round(weight, 3),
                        'shared_papers': shared_count,
                        'cross_citations': 0  # Simplified
                    })

    return jsonify({
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges)
    })
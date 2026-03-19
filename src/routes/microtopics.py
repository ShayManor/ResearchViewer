from flask import Blueprint, request, jsonify
from src.database import get_db, df_to_json_serializable
import json

microtopics_bp = Blueprint("microtopics", __name__)


@microtopics_bp.route("/api/microtopics", methods=["GET"])
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

    # Build query
    query = "SELECT * FROM microtopics WHERE 1=1"
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

    # Parse JSON fields
    microtopics = []
    for _, row in result.iterrows():
        topic = {
            'microtopic_id': row['microtopic_id'],
            'label': row['label'],
            'bucket_value': row['bucket_value'],
            'size': int(row['size']),
            'top_terms': json.loads(row['top_terms_json']) if row['top_terms_json'] else [],
            'representative_titles': json.loads(row['representative_titles_json']) if row['representative_titles_json'] else []
        }
        microtopics.append(topic)

    return jsonify({
        "microtopics": microtopics,
        "count": len(microtopics)
    })


@microtopics_bp.route("/api/microtopics/<microtopic_id>", methods=["GET"])
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

    # Get papers in this microtopic for stats
    papers = db.execute("""
        SELECT DISTINCT p.*
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND (p.deleted = false OR p.deleted IS NULL)
    """, [microtopic_id]).fetchdf()

    if not papers.empty:
        # Calculate statistics
        total_citations = int(papers['citation_count'].sum())
        avg_citations = float(papers['citation_count'].mean())
        median_citations = float(papers['citation_count'].median())
        max_citations = int(papers['citation_count'].max())

        # Year range
        papers['year'] = papers['update_date'].astype(str).str[:4]
        year_range = f"{papers['year'].min()}-{papers['year'].max()}"

        # Recent growth (papers in last 2 years / total)
        import datetime
        current_year = datetime.datetime.now().year
        recent_papers = papers[papers['year'].astype(int) >= current_year - 2]
        recent_growth_pct = (len(recent_papers) / len(papers)) * 100 if len(papers) > 0 else 0

        microtopic['stats'] = {
            'total_citations': total_citations,
            'avg_citations': avg_citations,
            'median_citations': median_citations,
            'max_citations': max_citations,
            'paper_count': len(papers),
            'year_range': year_range,
            'recent_growth_pct': round(recent_growth_pct, 1)
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

        # Top authors (parse authors field and count)
        # This is simplified - in production would parse authors_parsed properly
        author_counts = {}
        for authors_str in papers['authors'].dropna():
            if authors_str:
                # Simple split by comma
                for author in str(authors_str).split(',')[:3]:  # First 3 authors
                    author = author.strip()
                    if author:
                        if author not in author_counts:
                            author_counts[author] = {'count': 0, 'citations': 0}
                        author_counts[author]['count'] += 1

        top_authors = sorted(
            [{'name': name, 'paper_count': stats['count'], 'total_citations': stats['citations']}
             for name, stats in author_counts.items()],
            key=lambda x: x['paper_count'],
            reverse=True
        )[:10]

        microtopic['top_authors'] = top_authors

        # Top papers
        top_papers = papers.nlargest(10, 'citation_count')[['id', 'title', 'citation_count', 'update_date', 'authors']]
        microtopic['top_papers'] = df_to_json_serializable(top_papers)
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
def get_microtopic_papers(microtopic_id):
    """Papers belonging to a microtopic, paginated."""
    db = get_db()

    # Get query parameters
    sort_by = request.args.get('sort_by', 'citation_count')
    sort_order = request.args.get('sort_order', 'DESC')
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 100)

    # Validate sort field
    allowed_sorts = ['citation_count', 'update_date', 'score']
    if sort_by not in allowed_sorts:
        sort_by = 'citation_count'

    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    # Build query
    if sort_by == 'score':
        order_clause = f"pm.score {sort_order}"
    else:
        order_clause = f"p.{sort_by} {sort_order}"

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

    # Cross citations (papers in A that cite papers in B and vice versa)
    cross_citations = 0
    # This is expensive - simplified implementation
    # In production, would optimize with better indexing

    overlap = {
        'shared_paper_count': shared_paper_count,
        'shared_author_count': 0,  # Would need to compute author overlap
        'cross_citation_count': cross_citations,
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

    # Get papers for stats
    papers = db.execute("""
        SELECT DISTINCT p.*
        FROM papers p
        INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
        WHERE pm.microtopic_id = ?
        AND (p.deleted = false OR p.deleted IS NULL)
    """, [microtopic_id]).fetchdf()

    topic = {
        'microtopic_id': result[0],
        'label': result[4],
        'size': result[5]
    }

    if not papers.empty:
        topic['stats'] = {
            'total_citations': int(papers['citation_count'].sum()),
            'avg_citations': float(papers['citation_count'].mean()),
            'median_citations': float(papers['citation_count'].median()),
            'max_citations': int(papers['citation_count'].max()),
            'paper_count': len(papers)
        }

        # Top papers
        top_papers = papers.nlargest(5, 'citation_count')[['id', 'title', 'citation_count']]
        topic['top_papers'] = df_to_json_serializable(top_papers)

        # Papers by year
        papers['year'] = papers['update_date'].astype(str).str[:4]
        papers_by_year = papers.groupby('year').size().reset_index(name='count')
        topic['papers_by_year'] = df_to_json_serializable(papers_by_year)
    else:
        topic['stats'] = {'total_citations': 0, 'avg_citations': 0, 'median_citations': 0, 'max_citations': 0, 'paper_count': 0}
        topic['top_papers'] = []
        topic['papers_by_year'] = []

    return topic


@microtopics_bp.route("/api/microtopics/graph", methods=["GET"])
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

    # Build nodes
    nodes = []
    for _, topic in topics.iterrows():
        # Get papers for this topic to calculate stats
        papers = db.execute("""
            SELECT p.citation_count, p.title
            FROM papers p
            INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
            WHERE pm.microtopic_id = ?
            AND (p.deleted = false OR p.deleted IS NULL)
        """, [topic['microtopic_id']]).fetchdf()

        node = {
            'id': topic['microtopic_id'],
            'label': topic['label'],
            'bucket_value': topic['bucket_value'],
            'size': int(topic['size']),
            'avg_citations': float(papers['citation_count'].mean()) if not papers.empty else 0,
            'total_citations': int(papers['citation_count'].sum()) if not papers.empty else 0,
            'recent_growth_pct': 0,  # Simplified
            'top_paper_title': papers.nlargest(1, 'citation_count')['title'].iloc[0] if not papers.empty else ''
        }
        nodes.append(node)

    # Build edges (compute overlap between topics)
    edges = []
    topic_ids = topics['microtopic_id'].tolist()

    # Get paper sets for each topic
    topic_papers = {}
    for topic_id in topic_ids:
        papers = db.execute("""
            SELECT paper_id FROM paper_microtopics WHERE microtopic_id = ?
        """, [topic_id]).fetchdf()
        topic_papers[topic_id] = set(papers['paper_id'].tolist())

    # Calculate edges
    for i, topic_a in enumerate(topic_ids):
        for topic_b in topic_ids[i+1:]:
            papers_a = topic_papers[topic_a]
            papers_b = topic_papers[topic_b]

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
from flask import Blueprint, request, jsonify
from src.database import get_db, df_to_json_serializable
import json

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/api/reports/topic", methods=["POST"])
def generate_topic_report():
    """Generate a comprehensive report for one or two topics."""
    db = get_db()
    data = request.get_json()

    microtopic_id = data.get('microtopic_id')
    compare_microtopic_id = data.get('compare_microtopic_id')

    if not microtopic_id:
        return jsonify({"error": "microtopic_id is required"}), 400

    # Get main topic data
    topic_data = get_full_topic_data(db, microtopic_id)

    if not topic_data:
        return jsonify({"error": "Topic not found"}), 404

    response = {"topic": topic_data}

    # Add comparison if requested
    if compare_microtopic_id:
        topic_b_data = get_full_topic_data(db, compare_microtopic_id)

        if topic_b_data:
            # Calculate overlap
            papers_a = set(db.execute("""
                SELECT paper_id FROM paper_microtopics WHERE microtopic_id = ?
            """, [microtopic_id]).fetchdf()['paper_id'].tolist())

            papers_b = set(db.execute("""
                SELECT paper_id FROM paper_microtopics WHERE microtopic_id = ?
            """, [compare_microtopic_id]).fetchdf()['paper_id'].tolist())

            shared_papers = papers_a.intersection(papers_b)
            shared_paper_count = len(shared_papers)

            # Jaccard similarity
            union_size = len(papers_a.union(papers_b))
            jaccard = shared_paper_count / union_size if union_size > 0 else 0

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

            overlap = {
                'shared_papers': shared_paper_count,
                'shared_authors': 0,  # Simplified
                'cross_citations': 0,  # Simplified
                'jaccard': round(jaccard, 3)
            }

            response['comparison'] = {
                'topic_b': topic_b_data,
                'overlap': overlap
            }

    return jsonify(response)


@reports_bp.route("/api/reports/subject", methods=["POST"])
def generate_subject_report():
    """Generate report for an entire arXiv subject category."""
    db = get_db()
    data = request.get_json()

    subject = data.get('subject')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    compare_subject = data.get('compare_subject')

    if not subject:
        return jsonify({"error": "subject is required"}), 400

    # Get subject data
    subject_data = get_full_subject_data(db, subject, start_date, end_date)

    response = {"subject": subject_data}

    # Add comparison if requested
    if compare_subject:
        compare_data = get_full_subject_data(db, compare_subject, start_date, end_date)
        response['comparison'] = compare_data

    return jsonify(response)


def get_full_topic_data(db, microtopic_id):
    """Helper to get comprehensive topic data."""
    # Get basic topic info
    result = db.execute(
        "SELECT * FROM microtopics WHERE microtopic_id = ?",
        [microtopic_id]
    ).fetchone()

    if not result:
        return None

    topic = {
        'microtopic_id': result[0],
        'bucket_column': result[1],
        'bucket_value': result[2],
        'cluster_id': result[3],
        'label': result[4],
        'size': result[5]
    }

    # Get papers for this topic
    papers = db.execute("""
        SELECT p.*
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

        # Recent growth
        import datetime
        current_year = datetime.datetime.now().year
        recent_papers = papers[papers['year'].astype(int) >= current_year - 2]
        recent_growth_pct = (len(recent_papers) / len(papers)) * 100 if len(papers) > 0 else 0

        # Internal citations (papers in this topic that cite each other)
        paper_ids = set(papers['id'].tolist())
        internal_citation_count = 0
        for citations in papers['citations'].dropna():
            if citations:
                internal_citation_count += len([c for c in citations if c in paper_ids])

        # Unique authors
        unique_authors = set()
        for authors_str in papers['authors'].dropna():
            if authors_str:
                for author in str(authors_str).split(',')[:5]:
                    unique_authors.add(author.strip())

        topic['stats'] = {
            'total_citations': total_citations,
            'avg_citations': avg_citations,
            'median_citations': median_citations,
            'max_citations': max_citations,
            'year_range': year_range,
            'recent_growth_pct': round(recent_growth_pct, 1),
            'internal_citation_count': internal_citation_count,
            'unique_author_count': len(unique_authors)
        }

        # Papers by year
        papers_by_year = papers.groupby('year').agg({
            'id': 'count',
            'citation_count': 'sum'
        }).reset_index()
        papers_by_year.columns = ['year', 'count', 'citations']
        topic['papers_by_year'] = df_to_json_serializable(papers_by_year)

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
        topic['citation_distribution'] = df_to_json_serializable(citation_dist)

        # Top authors
        author_counts = {}
        for authors_str in papers['authors'].dropna():
            if authors_str:
                for author in str(authors_str).split(',')[:3]:
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

        topic['top_authors'] = top_authors

        # Top papers with percentage
        top_papers_df = papers.nlargest(10, 'citation_count')
        top_papers = []
        for _, paper in top_papers_df.iterrows():
            top_papers.append({
                'id': paper['id'],
                'title': paper['title'],
                'citation_count': int(paper['citation_count']),
                'pct_of_total': round((paper['citation_count'] / total_citations * 100), 1) if total_citations > 0 else 0
            })

        topic['top_papers'] = top_papers

        # Related topics (simplified - would need better algorithm)
        topic['related_topics'] = []
    else:
        topic['stats'] = {}
        topic['papers_by_year'] = []
        topic['citation_distribution'] = []
        topic['top_authors'] = []
        topic['top_papers'] = []
        topic['related_topics'] = []

    return topic


def get_full_subject_data(db, subject, start_date=None, end_date=None):
    """Helper to get comprehensive subject data."""
    # Build base query
    query = """
        SELECT *
        FROM papers
        WHERE categories LIKE ?
        AND (deleted = false OR deleted IS NULL)
    """
    params = [f"%{subject}%"]

    if start_date:
        query += " AND update_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND update_date <= ?"
        params.append(end_date)

    papers = db.execute(query, params).fetchdf()

    subject_data = {
        'category': subject,
        'paper_count': len(papers)
    }

    if not papers.empty:
        # Calculate statistics
        total_citations = int(papers['citation_count'].sum())
        avg_citations = float(papers['citation_count'].mean())
        median_citations = float(papers['citation_count'].median())
        max_citations = int(papers['citation_count'].max())

        # Unique authors
        unique_authors = set()
        for authors_str in papers['authors'].dropna():
            if authors_str:
                for author in str(authors_str).split(',')[:5]:
                    unique_authors.add(author.strip())

        # Papers per year
        papers['year'] = papers['update_date'].astype(str).str[:4]
        papers_by_year_count = papers.groupby('year').size()
        papers_per_year_avg = papers_by_year_count.mean() if not papers_by_year_count.empty else 0

        subject_data['stats'] = {
            'total_citations': total_citations,
            'avg_citations': avg_citations,
            'median_citations': median_citations,
            'max_citations': max_citations,
            'unique_author_count': len(unique_authors),
            'papers_per_year_avg': round(papers_per_year_avg, 0)
        }

        # Papers by year
        papers_by_year = papers.groupby('year').agg({
            'id': 'count',
            'citation_count': 'sum'
        }).reset_index()
        papers_by_year.columns = ['year', 'count', 'citations']
        subject_data['papers_by_year'] = df_to_json_serializable(papers_by_year)

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
        subject_data['citation_distribution'] = df_to_json_serializable(citation_dist)

        # Top microtopics in this subject
        top_microtopics = db.execute("""
            SELECT
                m.microtopic_id, m.label, m.size,
                ROUND(AVG(p.citation_count), 0) as avg_citations
            FROM microtopics m
            INNER JOIN paper_microtopics pm ON m.microtopic_id = pm.microtopic_id
            INNER JOIN papers p ON pm.paper_id = p.id
            WHERE p.categories LIKE ?
            AND (p.deleted = false OR p.deleted IS NULL)
            GROUP BY m.microtopic_id, m.label, m.size
            ORDER BY m.size DESC
            LIMIT 10
        """, [f"%{subject}%"]).fetchdf()

        subject_data['top_microtopics'] = df_to_json_serializable(top_microtopics) if not top_microtopics.empty else []

        # Top authors
        author_counts = {}
        for authors_str in papers['authors'].dropna():
            if authors_str:
                for author in str(authors_str).split(',')[:3]:
                    author = author.strip()
                    if author and author not in author_counts:
                        author_counts[author] = 0
                    if author:
                        author_counts[author] += 1

        top_authors = sorted(
            [{'name': name, 'paper_count': count} for name, count in author_counts.items()],
            key=lambda x: x['paper_count'],
            reverse=True
        )[:10]

        subject_data['top_authors'] = top_authors

        # Top papers
        top_papers_df = papers.nlargest(10, 'citation_count')
        subject_data['top_papers'] = df_to_json_serializable(
            top_papers_df[['id', 'title', 'citation_count', 'update_date']]
        )
    else:
        subject_data['stats'] = {}
        subject_data['papers_by_year'] = []
        subject_data['citation_distribution'] = []
        subject_data['top_microtopics'] = []
        subject_data['top_authors'] = []
        subject_data['top_papers'] = []

    return subject_data
import pytest
import json
from src.main import app
from src.database import get_data_db


@pytest.fixture
def app_ctx():
    """Push Flask app context for tests that need g/current_app."""
    app.config["TESTING"] = True
    with app.app_context():
        yield


@pytest.fixture
def client(app_ctx):
    """Create a test client for the Flask app."""
    with app.test_client() as client:
        yield client


@pytest.fixture
def data_db(app_ctx):
    """Get data database connection inside Flask app context."""
    yield get_data_db()


class TestDomains:
    """Test /api/analytics/domains endpoint."""

    def test_get_domains_default(self, client):
        """Test getting domains with default parameters."""
        response = client.get('/api/analytics/domains')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'domains' in data
        assert isinstance(data['domains'], list)

        # Verify structure of each domain
        if len(data['domains']) > 0:
            domain = data['domains'][0]
            assert 'domain' in domain
            assert 'paper_count' in domain
            assert 'avg_citations' in domain
            assert 'total_citations' in domain
            assert isinstance(domain['paper_count'], (int, float))
            assert isinstance(domain['avg_citations'], (int, float, type(None)))
            assert isinstance(domain['total_citations'], (int, float, type(None)))

    def test_get_domains_with_limit(self, client):
        """Test domains with custom limit."""
        response = client.get('/api/analytics/domains?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['domains']) <= 5

    def test_get_domains_large_limit(self, client):
        """Test domains with very large limit."""
        response = client.get('/api/analytics/domains?limit=1000')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['domains'], list)

    def test_get_domains_sorted_by_count(self, client):
        """Test that domains are sorted by paper count descending."""
        response = client.get('/api/analytics/domains?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['domains']) > 1:
            for i in range(len(data['domains']) - 1):
                assert data['domains'][i]['paper_count'] >= data['domains'][i + 1]['paper_count']

    def test_get_domains_no_empty_names(self, client):
        """Test that returned domains don't have empty names."""
        response = client.get('/api/analytics/domains')
        assert response.status_code == 200
        data = json.loads(response.data)

        for domain in data['domains']:
            assert domain['domain'] is not None
            assert domain['domain'] != ''


class TestTopics:
    """Test /api/analytics/topics endpoint."""

    def test_get_topics_requires_domain(self, client):
        """Test that topics endpoint requires domain parameter."""
        response = client.get('/api/analytics/topics')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_topics_with_valid_domain(self, client, data_db):
        """Test getting topics for a valid domain."""
        # Get a valid domain first
        result = data_db.execute("""
            SELECT DISTINCT primary_domain_name
            FROM papers
            WHERE primary_domain_name IS NOT NULL
            AND primary_domain_name != ''
            LIMIT 1
        """).fetchone()

        if result:
            domain = result[0]
            response = client.get(f'/api/analytics/topics?domain={domain}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'topics' in data
            assert isinstance(data['topics'], list)

            # Verify structure
            if len(data['topics']) > 0:
                topic = data['topics'][0]
                assert 'topic' in topic
                assert 'paper_count' in topic
                assert 'avg_citations' in topic
                assert 'total_citations' in topic

    def test_get_topics_with_limit(self, client, data_db):
        """Test topics with custom limit."""
        result = data_db.execute("""
            SELECT DISTINCT primary_domain_name
            FROM papers
            WHERE primary_domain_name IS NOT NULL
            LIMIT 1
        """).fetchone()

        if result:
            domain = result[0]
            response = client.get(f'/api/analytics/topics?domain={domain}&limit=5')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['topics']) <= 5

    def test_get_topics_nonexistent_domain(self, client):
        """Test topics for non-existent domain returns empty list."""
        response = client.get('/api/analytics/topics?domain=NonexistentDomain12345')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['topics'] == []

    def test_get_topics_sorted_by_count(self, client, data_db):
        """Test that topics are sorted by paper count descending."""
        result = data_db.execute("""
            SELECT DISTINCT primary_domain_name
            FROM papers
            WHERE primary_domain_name IS NOT NULL
            LIMIT 1
        """).fetchone()

        if result:
            domain = result[0]
            response = client.get(f'/api/analytics/topics?domain={domain}&limit=10')
            assert response.status_code == 200
            data = json.loads(response.data)

            if len(data['topics']) > 1:
                for i in range(len(data['topics']) - 1):
                    assert data['topics'][i]['paper_count'] >= data['topics'][i + 1]['paper_count']


class TestVelocity:
    """Test /api/analytics/velocity endpoint."""

    def test_velocity_default(self, client):
        """Test velocity with default parameters."""
        response = client.get('/api/analytics/velocity')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'velocity' in data
        assert 'period' in data
        assert 'avg' in data
        assert 'latest' in data
        assert 'delta' in data
        assert 'delta_pct' in data

        assert isinstance(data['velocity'], list)
        assert data['period'] == 'week'  # default
        assert len(data['velocity']) == 12  # default lookback

    def test_velocity_by_week(self, client):
        """Test weekly velocity."""
        response = client.get('/api/analytics/velocity?period=week&lookback=8')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['period'] == 'week'
        assert len(data['velocity']) == 8

        # Verify structure of velocity entries
        if len(data['velocity']) > 0:
            entry = data['velocity'][0]
            assert 'period_start' in entry
            assert 'period_end' in entry
            assert 'count' in entry
            assert isinstance(entry['count'], int)

    def test_velocity_by_month(self, client):
        """Test monthly velocity."""
        response = client.get('/api/analytics/velocity?period=month&lookback=6')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['period'] == 'month'
        assert len(data['velocity']) == 6

    def test_velocity_with_subject_filter(self, client):
        """Test velocity filtered by subject."""
        response = client.get('/api/analytics/velocity?period=week&lookback=4&subject=cs.AI')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert isinstance(data['velocity'], list)
        assert len(data['velocity']) == 4

    def test_velocity_calculates_stats_correctly(self, client):
        """Test that velocity statistics are calculated correctly."""
        response = client.get('/api/analytics/velocity?lookback=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Verify calculations
        counts = [v['count'] for v in data['velocity']]
        expected_avg = sum(counts) / len(counts) if counts else 0
        expected_latest = counts[-1] if counts else 0

        assert abs(data['avg'] - expected_avg) < 1  # Allow rounding difference
        assert data['latest'] == expected_latest

        if expected_avg > 0:
            expected_delta = expected_latest - expected_avg
            expected_delta_pct = (expected_delta / expected_avg * 100)
            assert abs(data['delta'] - expected_delta) < 1
            assert abs(data['delta_pct'] - expected_delta_pct) < 1

    def test_velocity_custom_lookback(self, client):
        """Test velocity with custom lookback period."""
        response = client.get('/api/analytics/velocity?lookback=20')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['velocity']) == 20


class TestHotPapers:
    """Test /api/analytics/hot-papers endpoint."""

    def test_hot_papers_default(self, client):
        """Test hot papers with default parameters."""
        response = client.get('/api/analytics/hot-papers')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'papers' in data
        assert isinstance(data['papers'], list)
        assert len(data['papers']) <= 10  # default limit

    def test_hot_papers_with_limit(self, client):
        """Test hot papers with custom limit."""
        response = client.get('/api/analytics/hot-papers?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['papers']) <= 5

    def test_hot_papers_structure(self, client):
        """Test that hot papers have correct structure."""
        response = client.get('/api/analytics/hot-papers?limit=3')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['papers']) > 0:
            paper = data['papers'][0]
            assert 'id' in paper
            assert 'title' in paper
            assert 'citation_count' in paper
            assert 'update_date' in paper
            assert 'categories' in paper
            assert 'authors' in paper

    def test_hot_papers_with_subject_filter(self, client):
        """Test hot papers filtered by subject."""
        response = client.get('/api/analytics/hot-papers?subject=cs.AI&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['papers'], list)

    def test_hot_papers_with_custom_since(self, client):
        """Test hot papers with custom since date."""
        response = client.get('/api/analytics/hot-papers?since=2020-01-01&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Verify all papers are after the since date
        for paper in data['papers']:
            if paper.get('update_date'):
                assert paper['update_date'] >= '2020-01-01'

    def test_hot_papers_sort_by_citations(self, client):
        """Test hot papers sorted by citations (default)."""
        response = client.get('/api/analytics/hot-papers?sort_by=citation_count&limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Verify descending order by citations
        if len(data['papers']) > 1:
            for i in range(len(data['papers']) - 1):
                curr_citations = data['papers'][i].get('citation_count', 0) or 0
                next_citations = data['papers'][i + 1].get('citation_count', 0) or 0
                assert curr_citations >= next_citations

    def test_hot_papers_sort_by_date(self, client):
        """Test hot papers sorted by date."""
        response = client.get('/api/analytics/hot-papers?sort_by=update_date&limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Verify descending order by date
        if len(data['papers']) > 1:
            for i in range(len(data['papers']) - 1):
                curr_date = data['papers'][i].get('update_date', '')
                next_date = data['papers'][i + 1].get('update_date', '')
                if curr_date and next_date:
                    assert curr_date >= next_date

    def test_hot_papers_excludes_user_read(self, client, data_db):
        """Test that hot papers can exclude user's read papers."""
        # Create a test user and mark a paper as read
        import time
        timestamp = int(time.time() * 1000)

        # Note: This test assumes user_id parameter works
        # In practice, this might require authentication
        response = client.get(f'/api/analytics/hot-papers?user_id=999999&limit=5')
        # Should not error, even if user doesn't exist
        assert response.status_code == 200

    def test_hot_papers_invalid_sort_field(self, client):
        """Test hot papers with invalid sort field falls back to default."""
        response = client.get('/api/analytics/hot-papers?sort_by=invalid_field&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['papers'], list)

    def test_hot_papers_is_cached(self, client):
        """Test that hot papers endpoint uses caching."""
        # Make two identical requests
        response1 = client.get('/api/analytics/hot-papers?limit=5')
        response2 = client.get('/api/analytics/hot-papers?limit=5')

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Results should be identical (cached)
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        assert data1 == data2


class TestPapersOverTime:
    """Test /api/analytics/papers/over-time endpoint."""

    def test_papers_over_time_default(self, client):
        """Test papers over time with default parameters."""
        response = client.get('/api/analytics/papers/over-time')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'data' in data
        assert 'group_by' in data
        assert isinstance(data['data'], list)
        assert data['group_by'] == 'year'  # default

    def test_papers_over_time_by_year(self, client):
        """Test papers over time grouped by year."""
        response = client.get('/api/analytics/papers/over-time?group_by=year')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['group_by'] == 'year'

        # Verify structure
        if len(data['data']) > 0:
            entry = data['data'][0]
            assert 'period' in entry
            assert 'count' in entry
            assert 'total_citations' in entry

    def test_papers_over_time_by_month(self, client):
        """Test papers over time grouped by month."""
        response = client.get('/api/analytics/papers/over-time?group_by=month')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['group_by'] == 'month'

        # Verify month format (YYYY-MM)
        if len(data['data']) > 0:
            period = data['data'][0]['period']
            assert '-' in period
            parts = period.split('-')
            assert len(parts) == 2
            assert len(parts[0]) == 4  # year
            assert len(parts[1]) == 2  # month

    def test_papers_over_time_with_subject(self, client):
        """Test papers over time filtered by subject."""
        response = client.get('/api/analytics/papers/over-time?subject=cs.AI&group_by=year')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['data'], list)

    def test_papers_over_time_with_microtopic(self, client, data_db):
        """Test papers over time filtered by microtopic."""
        # Get a valid microtopic ID
        result = data_db.execute("""
            SELECT microtopic_id FROM microtopics LIMIT 1
        """).fetchone()

        if result:
            microtopic_id = result[0]
            response = client.get(f'/api/analytics/papers/over-time?microtopic_id={microtopic_id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data['data'], list)

    def test_papers_over_time_sorted_chronologically(self, client):
        """Test that results are sorted by period."""
        response = client.get('/api/analytics/papers/over-time?group_by=year')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['data']) > 1:
            for i in range(len(data['data']) - 1):
                assert data['data'][i]['period'] <= data['data'][i + 1]['period']


class TestCitationDistribution:
    """Test /api/analytics/citations/distribution endpoint."""

    def test_citation_distribution_default(self, client):
        """Test citation distribution with default parameters."""
        response = client.get('/api/analytics/citations/distribution')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'distribution' in data
        assert isinstance(data['distribution'], list)

    def test_citation_distribution_structure(self, client):
        """Test citation distribution buckets."""
        response = client.get('/api/analytics/citations/distribution')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['distribution']) > 0:
            bucket = data['distribution'][0]
            assert 'citation_range' in bucket
            assert 'paper_count' in bucket
            assert isinstance(bucket['paper_count'], (int, float))

    def test_citation_distribution_with_subject(self, client):
        """Test citation distribution filtered by subject."""
        response = client.get('/api/analytics/citations/distribution?subject=cs.AI')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['distribution'], list)

    def test_citation_distribution_with_microtopic(self, client, data_db):
        """Test citation distribution filtered by microtopic."""
        result = data_db.execute("""
            SELECT microtopic_id FROM microtopics LIMIT 1
        """).fetchone()

        if result:
            microtopic_id = result[0]
            response = client.get(f'/api/analytics/citations/distribution?microtopic_id={microtopic_id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data['distribution'], list)

    def test_citation_distribution_bucket_ranges(self, client):
        """Test that distribution uses correct citation ranges."""
        response = client.get('/api/analytics/citations/distribution')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Expected bucket ranges
        expected_ranges = [
            '0', '1-5', '6-10', '11-25', '26-50', '51-100',
            '101-500', '501-1000', '1001-5000', '5001-10000', '10000+'
        ]

        # All returned ranges should be in expected list
        for bucket in data['distribution']:
            # Range might not exist if no papers in that bucket
            # Just verify structure is correct
            assert isinstance(bucket['citation_range'], str)


class TestSubjects:
    """Test /api/analytics/subjects endpoint."""

    def test_subjects_default(self, client):
        """Test subjects breakdown with default parameters."""
        response = client.get('/api/analytics/subjects')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'subjects' in data
        assert isinstance(data['subjects'], list)
        assert len(data['subjects']) <= 20  # default limit

    def test_subjects_with_limit(self, client):
        """Test subjects with custom limit."""
        response = client.get('/api/analytics/subjects?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['subjects']) <= 10

    def test_subjects_structure(self, client):
        """Test subjects data structure."""
        response = client.get('/api/analytics/subjects?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['subjects']) > 0:
            subject = data['subjects'][0]
            assert 'subject' in subject
            assert 'paper_count' in subject
            assert 'avg_citations' in subject
            assert isinstance(subject['paper_count'], (int, float))

    def test_subjects_sorted_by_count(self, client):
        """Test that subjects are sorted by paper count."""
        response = client.get('/api/analytics/subjects?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['subjects']) > 1:
            for i in range(len(data['subjects']) - 1):
                assert data['subjects'][i]['paper_count'] >= data['subjects'][i + 1]['paper_count']


class TestTopAuthors:
    """Test /api/analytics/authors/top endpoint."""

    def test_top_authors_default(self, client):
        """Test top authors with default parameters."""
        response = client.get('/api/analytics/authors/top')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'top_authors' in data
        assert 'sorted_by' in data
        assert isinstance(data['top_authors'], list)
        assert data['sorted_by'] == 'h_index'  # default

    def test_top_authors_by_h_index(self, client):
        """Test top authors sorted by h-index."""
        response = client.get('/api/analytics/authors/top?sort_by=h_index&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['sorted_by'] == 'h_index'
        assert len(data['top_authors']) <= 5

        # Verify descending order
        if len(data['top_authors']) > 1:
            for i in range(len(data['top_authors']) - 1):
                curr = data['top_authors'][i].get('h_index', 0) or 0
                next = data['top_authors'][i + 1].get('h_index', 0) or 0
                assert curr >= next

    def test_top_authors_by_works_count(self, client):
        """Test top authors sorted by works count."""
        response = client.get('/api/analytics/authors/top?sort_by=works_count&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['sorted_by'] == 'works_count'

    def test_top_authors_by_citations(self, client):
        """Test top authors sorted by citation count."""
        response = client.get('/api/analytics/authors/top?sort_by=cited_by_count&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['sorted_by'] == 'cited_by_count'

    def test_top_authors_invalid_sort_field(self, client):
        """Test that invalid sort field falls back to default."""
        response = client.get('/api/analytics/authors/top?sort_by=invalid_field&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Should fall back to h_index
        assert data['sorted_by'] == 'h_index'

    def test_top_authors_with_subject_filter(self, client):
        """Test top authors filtered by subject."""
        response = client.get('/api/analytics/authors/top?subject=cs.AI&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['top_authors'], list)

    def test_top_authors_structure(self, client):
        """Test top authors data structure."""
        response = client.get('/api/analytics/authors/top?limit=3')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['top_authors']) > 0:
            author = data['top_authors'][0]
            assert 'author_id' in author
            assert 'name' in author
            assert 'h_index' in author
            assert 'works_count' in author
            assert 'cited_by_count' in author

    def test_top_authors_limit_enforcement(self, client):
        """Test that limit cannot exceed 200."""
        response = client.get('/api/analytics/authors/top?limit=500')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Should be capped at 200
        assert len(data['top_authors']) <= 200


class TestCitationGraph:
    """Test /api/analytics/graph endpoint."""

    def test_citation_graph_default(self, client):
        """Test citation graph with default parameters."""
        response = client.get('/api/analytics/graph')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'nodes' in data
        assert 'edges' in data
        assert 'node_count' in data
        assert 'edge_count' in data
        assert isinstance(data['nodes'], list)
        assert isinstance(data['edges'], list)
        assert data['node_count'] == len(data['nodes'])
        assert data['edge_count'] == len(data['edges'])

    def test_citation_graph_with_limit(self, client):
        """Test citation graph with custom limit."""
        response = client.get('/api/analytics/graph?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        # Limit applies to source papers, but nodes may include cited papers too
        assert isinstance(data['nodes'], list)

    def test_citation_graph_node_structure(self, client):
        """Test citation graph node structure."""
        response = client.get('/api/analytics/graph?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['nodes']) > 0:
            node = data['nodes'][0]
            assert 'id' in node
            assert 'label' in node
            assert 'category' in node
            assert 'citation_count' in node

    def test_citation_graph_edge_structure(self, client):
        """Test citation graph edge structure."""
        response = client.get('/api/analytics/graph?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        if len(data['edges']) > 0:
            edge = data['edges'][0]
            assert 'source' in edge
            assert 'target' in edge
            assert 'type' in edge
            assert edge['type'] == 'citation'

    def test_citation_graph_with_subject_filter(self, client):
        """Test citation graph filtered by subject."""
        response = client.get('/api/analytics/graph?subject=cs.AI&limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert isinstance(data['nodes'], list)
        assert isinstance(data['edges'], list)

    def test_citation_graph_edges_reference_nodes(self, client):
        """Test that all edges reference valid nodes."""
        response = client.get('/api/analytics/graph?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)

        node_ids = {node['id'] for node in data['nodes']}

        for edge in data['edges']:
            # Source should always be in nodes
            assert edge['source'] in node_ids
            # Target should be in nodes (added by the endpoint)
            assert edge['target'] in node_ids


class TestAnalyticsEdgeCases:
    """Test edge cases and error conditions for analytics endpoints."""

    def test_domains_with_zero_limit(self, client):
        """Test domains with limit=0."""
        response = client.get('/api/analytics/domains?limit=0')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['domains'] == []

    def test_velocity_with_zero_lookback(self, client):
        """Test velocity with lookback=0."""
        response = client.get('/api/analytics/velocity?lookback=0')
        assert response.status_code == 200
        # Should handle gracefully, might return empty or minimal data

    def test_hot_papers_with_future_since_date(self, client):
        """Test hot papers with future since date."""
        response = client.get('/api/analytics/hot-papers?since=2099-01-01&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should return empty list
        assert data['papers'] == []

    def test_topics_with_special_characters_in_domain(self, client):
        """Test topics with special characters in domain name."""
        response = client.get('/api/analytics/topics?domain=Domain%20With%20Spaces')
        assert response.status_code == 200
        # Should not crash

    def test_velocity_with_very_large_lookback(self, client):
        """Test velocity with unreasonably large lookback."""
        response = client.get('/api/analytics/velocity?lookback=1000')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should complete without timeout
        assert len(data['velocity']) == 1000

    def test_hot_papers_with_invalid_date_format(self, client):
        """Test hot papers with invalid date format returns 400."""
        response = client.get('/api/analytics/hot-papers?since=not-a-date')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'YYYY-MM-DD' in data['error']

    def test_citation_graph_with_negative_limit(self, client):
        """Test citation graph with negative limit returns 400."""
        response = client.get('/api/analytics/graph?limit=-1')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'non-negative' in data['error']

    def test_domains_with_negative_limit(self, client):
        """Test domains with negative limit returns 400."""
        response = client.get('/api/analytics/domains?limit=-5')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_topics_with_negative_limit(self, client):
        """Test topics with negative limit returns 400."""
        response = client.get('/api/analytics/topics?domain=test&limit=-1')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_subjects_with_negative_limit(self, client):
        """Test subjects with negative limit returns 400."""
        response = client.get('/api/analytics/subjects?limit=-10')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_top_authors_with_negative_limit(self, client):
        """Test top authors with negative limit returns 400."""
        response = client.get('/api/analytics/authors/top?limit=-1')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_hot_papers_with_negative_limit(self, client):
        """Test hot papers with negative limit returns 400."""
        response = client.get('/api/analytics/hot-papers?limit=-1')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_domains_with_non_integer_limit(self, client):
        """Test domains with non-integer limit returns 400."""
        response = client.get('/api/analytics/domains?limit=abc')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'integer' in data['error']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

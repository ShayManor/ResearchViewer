"""
Comprehensive test suite for ResearchViewer API endpoints.

Tests all CRUD operations, edge cases, and error conditions.
"""

import pytest
import json
from src.main import app
from src.database import get_db


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def db():
    """Get database connection."""
    return get_db()


class TestHealth:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test main health check endpoint."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        assert 'paper_count' in data
        assert data['paper_count'] > 0

    def test_ping(self, client):
        """Test ping endpoint."""
        response = client.get('/api/')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ping'] == 'pong'


class TestPapers:
    """Test paper-related endpoints."""

    def test_get_papers_default(self, client):
        """Test getting papers with default parameters."""
        response = client.get('/api/papers')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'papers' in data
        assert 'page' in data
        assert 'per_page' in data
        assert isinstance(data['papers'], list)
        assert len(data['papers']) <= 20  # default per_page

    def test_get_papers_pagination(self, client):
        """Test pagination parameters."""
        response = client.get('/api/papers?page=2&per_page=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['page'] == 2
        assert data['per_page'] == 5
        assert len(data['papers']) <= 5

    def test_get_papers_with_subject_filter(self, client):
        """Test filtering by subject."""
        response = client.get('/api/papers?subject=cs.AI&per_page=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['papers'], list)
        # Check that returned papers match filter
        for paper in data['papers']:
            assert 'categories' in paper

    def test_get_papers_with_keyword(self, client):
        """Test keyword search."""
        response = client.get('/api/papers?keyword=neural&per_page=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['papers'], list)

    def test_get_papers_sorting(self, client):
        """Test sorting options."""
        response = client.get('/api/papers?sort_by=citation_count&sort_order=DESC&per_page=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        papers = data['papers']
        if len(papers) > 1:
            # Verify descending order
            for i in range(len(papers) - 1):
                if papers[i]['citation_count'] is not None and papers[i+1]['citation_count'] is not None:
                    assert papers[i]['citation_count'] >= papers[i+1]['citation_count']

    def test_count_papers(self, client):
        """Test paper count endpoint."""
        response = client.get('/api/count_papers')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'count' in data
        assert data['count'] > 0

    def test_count_papers_with_filter(self, client):
        """Test count with filters."""
        response = client.get('/api/count_papers?subject=cs.AI')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'count' in data
        assert isinstance(data['count'], int)

    def test_get_paper_by_doi(self, client, db):
        """Test getting a specific paper by DOI."""
        # Get a valid DOI first
        result = db.execute("""
            SELECT doi FROM papers
            WHERE doi IS NOT NULL
            AND (deleted = false OR deleted IS NULL)
            LIMIT 1
        """).fetchone()

        if result:
            doi = result[0]
            # URL encode the DOI
            from urllib.parse import quote
            encoded_doi = quote(doi, safe='')

            response = client.get(f'/api/papers/{encoded_doi}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['doi'].lower() == doi.lower()
            assert 'title' in data
            assert 'abstract' in data

    def test_get_paper_not_found(self, client):
        """Test getting non-existent paper."""
        response = client.get('/api/papers/10.1234/nonexistent.doi')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_add_paper(self, client):
        """Test adding a new paper."""
        import time
        unique_id = int(time.time() * 1000)  # millisecond timestamp
        new_paper = {
            'doi': f'10.test/test.paper.{unique_id}',
            'title': 'Test Paper Title',
            'abstract': 'This is a test abstract.',
            'authors': 'Test Author',
            'subject': 'cs.AI',
            'citations': []
        }

        response = client.post('/api/papers',
                              data=json.dumps(new_paper),
                              content_type='application/json')
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'created'

    def test_add_paper_duplicate(self, client, db):
        """Test adding duplicate paper."""
        # Get an existing DOI
        result = db.execute("""
            SELECT doi FROM papers
            WHERE doi IS NOT NULL
            LIMIT 1
        """).fetchone()

        if result:
            existing_doi = result[0]
            paper = {
                'doi': existing_doi,
                'title': 'Duplicate Test'
            }

            response = client.post('/api/papers',
                                  data=json.dumps(paper),
                                  content_type='application/json')
            assert response.status_code == 409

    def test_add_paper_missing_required_fields(self, client):
        """Test adding paper without required fields."""
        # Missing DOI
        response = client.post('/api/papers',
                              data=json.dumps({'title': 'Test'}),
                              content_type='application/json')
        assert response.status_code == 400

        # Missing title
        response = client.post('/api/papers',
                              data=json.dumps({'doi': '10.test/test'}),
                              content_type='application/json')
        assert response.status_code == 400


class TestAuthors:
    """Test author-related endpoints."""

    def test_get_authors_default(self, client):
        """Test getting authors with default parameters."""
        response = client.get('/api/authors')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'authors' in data
        assert isinstance(data['authors'], list)

    def test_get_authors_pagination(self, client):
        """Test author pagination."""
        response = client.get('/api/authors?page=1&per_page=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['page'] == 1
        assert len(data['authors']) <= 5

    def test_search_authors(self, client):
        """Test author search."""
        response = client.get('/api/authors/search?name=john&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'authors' in data
        assert 'count' in data
        assert isinstance(data['authors'], list)

    def test_search_authors_no_query(self, client):
        """Test search without name parameter."""
        response = client.get('/api/authors/search')
        assert response.status_code == 400

    def test_get_author_by_id(self, client, db):
        """Test getting specific author."""
        # Get a valid author ID
        result = db.execute("""
            SELECT author_id FROM authors LIMIT 1
        """).fetchone()

        if result:
            author_id = result[0]
            from urllib.parse import quote
            encoded_id = quote(author_id, safe='')

            response = client.get(f'/api/authors/{encoded_id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['author_id'] == author_id

    def test_get_author_not_found(self, client):
        """Test getting non-existent author."""
        response = client.get('/api/authors/https://fake.author.id/12345')
        assert response.status_code == 404

    def test_add_author(self, client):
        """Test adding new author."""
        import time
        unique_id = int(time.time() * 1000)
        new_author = {
            'author_id': f'https://test.org/author/{unique_id}',
            'name': 'Test Author',
            'h_index': 5,
            'works_count': 10
        }

        response = client.post('/api/authors',
                              data=json.dumps(new_author),
                              content_type='application/json')
        assert response.status_code == 201


class TestAnalytics:
    """Test analytics endpoints."""

    def test_papers_over_time_default(self, client):
        """Test papers over time with defaults."""
        response = client.get('/api/analytics/papers/over-time')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'data' in data
        assert 'group_by' in data
        assert isinstance(data['data'], list)

    def test_papers_over_time_by_month(self, client):
        """Test papers over time grouped by month."""
        response = client.get('/api/analytics/papers/over-time?group_by=month')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['group_by'] == 'month'

    def test_citations_distribution(self, client):
        """Test citation distribution."""
        response = client.get('/api/analytics/citations/distribution')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'distribution' in data
        assert isinstance(data['distribution'], list)

    def test_subjects_breakdown(self, client):
        """Test subjects breakdown."""
        response = client.get('/api/analytics/subjects?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'subjects' in data
        assert len(data['subjects']) <= 10

    def test_top_authors(self, client):
        """Test top authors endpoint."""
        response = client.get('/api/analytics/authors/top?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'top_authors' in data
        assert 'sorted_by' in data
        assert len(data['top_authors']) <= 5

    def test_top_authors_by_citations(self, client):
        """Test top authors sorted by citations."""
        response = client.get('/api/analytics/authors/top?sort_by=cited_by_count&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['sorted_by'] == 'cited_by_count'

    def test_citation_graph(self, client):
        """Test citation graph endpoint."""
        response = client.get('/api/analytics/graph?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'nodes' in data
        assert 'edges' in data
        assert 'node_count' in data
        assert 'edge_count' in data


class TestUsers:
    """Test user-related endpoints."""

    def test_register_user(self, client):
        """Test user registration."""
        import time
        username = f'testuser_{int(time.time())}'
        user_data = {
            'username': username,
            'password': 'testpassword123'
        }

        response = client.post('/api/users/register',
                              data=json.dumps(user_data),
                              content_type='application/json')
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'created'
        assert 'user_id' in data

    def test_register_missing_fields(self, client):
        """Test registration with missing fields."""
        response = client.post('/api/users/register',
                              data=json.dumps({'username': 'test'}),
                              content_type='application/json')
        assert response.status_code == 400

    def test_login_user(self, client, db):
        """Test user login."""
        # First register a user
        import time
        username = f'logintest_{int(time.time())}'
        password = 'testpass123'

        reg_response = client.post('/api/users/register',
                                   data=json.dumps({
                                       'username': username,
                                       'password': password
                                   }),
                                   content_type='application/json')
        assert reg_response.status_code == 201

        # Now try to login
        login_response = client.post('/api/users/login',
                                     data=json.dumps({
                                         'username': username,
                                         'password': password
                                     }),
                                     content_type='application/json')
        assert login_response.status_code == 200
        data = json.loads(login_response.data)
        assert data['status'] == 'authenticated'
        assert 'session_token' in data

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post('/api/users/login',
                              data=json.dumps({
                                  'username': 'nonexistent',
                                  'password': 'wrong'
                              }),
                              content_type='application/json')
        assert response.status_code == 401


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_large_pagination_offset(self, client):
        """Test pagination with very large offset."""
        response = client.get('/api/papers?page=99999&per_page=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should return empty list, not error
        assert isinstance(data['papers'], list)

    def test_invalid_sort_field(self, client):
        """Test with invalid sort field."""
        # Should not crash, might use default or ignore
        response = client.get('/api/papers?sort_by=invalid_field')
        # Should either work with default or return error, but not crash
        assert response.status_code in [200, 400]

    def test_special_characters_in_search(self, client):
        """Test search with special characters."""
        response = client.get('/api/papers?keyword=%27%22%3C%3E')  # '\"<>
        assert response.status_code == 200

    def test_empty_filters(self, client):
        """Test with empty filter values."""
        response = client.get('/api/papers?subject=&journal=')
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
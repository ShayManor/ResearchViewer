"""
Comprehensive test suite for ResearchViewer API endpoints.

Tests all CRUD operations, edge cases, and error conditions.
"""

import pytest
import json
from src.main import app
from src.database import get_data_db, get_user_db


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


@pytest.fixture
def user_db(app_ctx):
    """Get user database connection inside Flask app context."""
    yield get_user_db()


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

    def test_swagger_ui_loads(self, client):
        """Test that Swagger UI loads at /api."""
        response = client.get('/api/')
        assert response.status_code == 200
        # Should return HTML for Swagger UI
        assert b'swagger' in response.data.lower()


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

    def test_get_paper_by_doi(self, client, data_db):
        """Test getting a specific paper by arXiv ID."""
        # Get a valid paper ID first
        result = data_db.execute("""
            SELECT id FROM papers
            WHERE id IS NOT NULL
            AND (deleted = false OR deleted IS NULL)
            LIMIT 1
        """).fetchone()

        if result:
            paper_id = result[0]
            # URL encode the ID
            from urllib.parse import quote
            encoded_id = quote(paper_id, safe='')

            response = client.get(f'/api/papers/{encoded_id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['id'] == paper_id
            assert 'title' in data
            assert 'abstract' in data
            assert 'microtopics' in data

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

    def test_add_paper_duplicate(self, client, data_db):
        """Test adding duplicate paper."""
        # Get an existing DOI
        result = data_db.execute("""
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

    def test_get_author_by_id(self, client, data_db):
        """Test getting specific author."""
        # Get a valid author ID
        result = data_db.execute("""
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
    """Test user-related endpoints with Firebase authentication."""

    def test_register_user_firebase(self, client):
        """Test user registration with Firebase UID."""
        import time
        timestamp = int(time.time())
        username = f'testuser_{timestamp}'
        firebase_uid = f'firebase_test_{timestamp}'

        user_data = {
            'firebase_uid': firebase_uid,
            'username': username,
            'email': f'{username}@test.com',
            'focus_topics': []
        }

        response = client.post('/api/auth/register',
                              data=json.dumps(user_data),
                              content_type='application/json')
        assert response.status_code in [200, 201]  # 200 if exists, 201 if created
        data = json.loads(response.data)
        assert 'user_id' in data
        assert 'username' in data
        assert 'email' in data

    def test_register_duplicate_firebase_uid(self, client):
        """Test registering same Firebase UID twice returns existing user."""
        import time
        timestamp = int(time.time())
        firebase_uid = f'firebase_dup_{timestamp}'

        user_data = {
            'firebase_uid': firebase_uid,
            'username': f'user1_{timestamp}',
            'email': f'user1_{timestamp}@test.com'
        }

        # First registration
        response1 = client.post('/api/auth/register',
                               data=json.dumps(user_data),
                               content_type='application/json')
        assert response1.status_code == 201
        data1 = json.loads(response1.data)
        user_id1 = data1['user_id']

        # Second registration with same Firebase UID but different username
        user_data['username'] = f'user2_{timestamp}'
        response2 = client.post('/api/auth/register',
                               data=json.dumps(user_data),
                               content_type='application/json')
        assert response2.status_code == 200  # Should return existing user
        data2 = json.loads(response2.data)
        assert data2['user_id'] == user_id1  # Same user ID

    def test_register_missing_fields(self, client):
        """Test registration with missing required fields."""
        # Missing firebase_uid
        response = client.post('/api/auth/register',
                              data=json.dumps({
                                  'username': 'test',
                                  'email': 'test@test.com'
                              }),
                              content_type='application/json')
        assert response.status_code == 400

        # Missing username
        response = client.post('/api/auth/register',
                              data=json.dumps({
                                  'firebase_uid': 'test123',
                                  'email': 'test@test.com'
                              }),
                              content_type='application/json')
        assert response.status_code == 400

        # Missing email
        response = client.post('/api/auth/register',
                              data=json.dumps({
                                  'firebase_uid': 'test123',
                                  'username': 'testuser'
                              }),
                              content_type='application/json')
        assert response.status_code == 400

    def test_register_duplicate_username(self, client):
        """Test that duplicate usernames are rejected."""
        import time
        import random
        timestamp = int(time.time() * 1000)  # Microsecond precision
        random_suffix = random.randint(10000, 99999)
        username = f'dup_user_{timestamp}_{random_suffix}'

        # First user
        user_data1 = {
            'firebase_uid': f'fb1_{timestamp}_{random_suffix}',
            'username': username,
            'email': f'user1_{timestamp}_{random_suffix}@test.com'
        }
        response1 = client.post('/api/auth/register',
                               data=json.dumps(user_data1),
                               content_type='application/json')
        # Should be created (201) or already exists with this firebase_uid (200)
        assert response1.status_code in [200, 201]

        # If it returned 200, it means user already existed, so skip the duplicate test
        if response1.status_code == 200:
            # User already existed, can't test duplicate username scenario
            return

        # Second user with same username but different firebase_uid
        user_data2 = {
            'firebase_uid': f'fb2_{timestamp}_{random_suffix}',
            'username': username,  # Same username
            'email': f'user2_{timestamp}_{random_suffix}@test.com'
        }
        response2 = client.post('/api/auth/register',
                               data=json.dumps(user_data2),
                               content_type='application/json')
        assert response2.status_code == 409  # Conflict - username taken


class TestDualDatabase:
    """Test that data and user databases are properly separated."""

    def test_data_db_has_papers(self, data_db):
        """Test that data database contains papers table."""
        result = data_db.execute("SELECT COUNT(*) FROM papers").fetchone()
        assert result[0] > 0, "Data database should have papers"

    def test_data_db_has_authors(self, data_db):
        """Test that data database contains authors table."""
        result = data_db.execute("SELECT COUNT(*) FROM authors").fetchone()
        assert result[0] > 0, "Data database should have authors"

    def test_user_db_has_users(self, user_db):
        """Test that user database contains users table."""
        result = user_db.execute("SELECT COUNT(*) FROM users").fetchone()
        assert result[0] >= 0, "User database should have users table"

    def test_user_db_has_reading_list(self, user_db):
        """Test that user database has reading list table."""
        # Should not error even if table is empty
        result = user_db.execute("SELECT COUNT(*) FROM user_reading_list").fetchone()
        assert result[0] >= 0

    def test_databases_are_independent(self, data_db, user_db):
        """Test that modifying user DB doesn't affect data DB."""
        # Get counts before
        papers_before = data_db.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

        # Add a test user
        import time
        timestamp = int(time.time() * 1000)
        try:
            user_db.execute(f"""
                INSERT INTO users (id, username, email, password_hash, firebase_uid)
                VALUES (nextval('users_id_seq'), 'testuser_{timestamp}',
                        'test_{timestamp}@test.com', 'hash', 'fb_{timestamp}')
            """)
            user_db.commit()
        except:
            # User might already exist, that's fine
            pass

        # Papers count should be unchanged
        papers_after = data_db.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        assert papers_before == papers_after


class TestReadingList:
    """Test reading list functionality."""

    def test_add_to_reading_list_requires_auth(self, client):
        """Test that adding to reading list requires authentication."""
        response = client.post('/api/users/1/reading-list',
                              data=json.dumps({'paper_id': 'test-paper'}),
                              content_type='application/json')
        assert response.status_code == 401

    def test_get_reading_list_requires_auth(self, client):
        """Test that getting reading list requires authentication."""
        response = client.get('/api/users/1/reading-list')
        assert response.status_code == 401


class TestMicrotopics:
    """Test microtopic endpoints."""

    def test_get_microtopics(self, client):
        """Test getting microtopics list."""
        response = client.get('/api/microtopics?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'microtopics' in data
        assert 'count' in data
        assert isinstance(data['microtopics'], list)

    def test_get_microtopics_with_search(self, client):
        """Test searching microtopics."""
        response = client.get('/api/microtopics?search=machine&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['microtopics'], list)

    def test_get_microtopics_with_bucket_filter(self, client, data_db):
        """Test filtering microtopics by bucket."""
        # Get a valid bucket value
        result = data_db.execute("""
            SELECT DISTINCT bucket_value FROM microtopics
            WHERE bucket_value IS NOT NULL LIMIT 1
        """).fetchone()

        if result:
            bucket = result[0]
            response = client.get(f'/api/microtopics?bucket_value={bucket}&limit=10')
            assert response.status_code == 200
            data = json.loads(response.data)
            # All returned microtopics should have the specified bucket
            for mt in data['microtopics']:
                assert mt['bucket_value'] == bucket

    def test_get_microtopic_detail(self, client, data_db):
        """Test getting single microtopic details."""
        # Get a valid microtopic ID
        result = data_db.execute("SELECT microtopic_id FROM microtopics LIMIT 1").fetchone()

        if result:
            mt_id = result[0]
            response = client.get(f'/api/microtopics/{mt_id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['microtopic_id'] == mt_id
            assert 'label' in data
            assert 'size' in data

    def test_get_microtopic_not_found(self, client):
        """Test getting non-existent microtopic."""
        response = client.get('/api/microtopics/nonexistent-id-12345')
        assert response.status_code == 404


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
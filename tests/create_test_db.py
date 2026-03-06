"""
Create a lightweight test database with minimal data for CI/CD testing.

This script creates a small DuckDB database with the same schema as production
but with only a handful of test records.
"""

import duckdb
import os

# Path for test database
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), 'test_data.db')


def create_test_database():
    """Create test database with schema and sample data."""

    # Remove existing test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    conn = duckdb.connect(TEST_DB_PATH)

    # Create papers table
    conn.execute("""
        CREATE TABLE papers (
            id VARCHAR,
            submitter VARCHAR,
            authors VARCHAR,
            title VARCHAR,
            comments VARCHAR,
            "journal-ref" VARCHAR,
            doi VARCHAR,
            "report-no" VARCHAR,
            categories VARCHAR,
            license VARCHAR,
            abstract VARCHAR,
            versions STRUCT("version" VARCHAR, created VARCHAR)[],
            update_date DATE,
            authors_parsed VARCHAR[][],
            author_ids VARCHAR[],
            deleted BOOLEAN,
            citations VARCHAR[],
            citation_count INTEGER
        )
    """)

    # Create authors table
    conn.execute("""
        CREATE TABLE authors (
            author_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            paper_dois VARCHAR[],
            h_index INTEGER,
            works_count INTEGER,
            cited_by_count INTEGER
        )
    """)

    # Create users table
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR UNIQUE NOT NULL,
            password_hash VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create user-related tables
    conn.execute("""
        CREATE TABLE user_subjects (
            user_id INTEGER,
            subject VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE user_read_papers (
            user_id INTEGER,
            doi VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE user_candidates (
            user_id INTEGER,
            doi VARCHAR
        )
    """)

    # Insert sample papers
    sample_papers = [
        {
            'id': '2024.12345',
            'submitter': 'Test Submitter',
            'authors': 'Alice Smith, Bob Jones',
            'title': 'Sample Paper on Machine Learning',
            'comments': None,
            'journal-ref': 'Test Journal 2024',
            'doi': '10.1234/test.paper.001',
            'report-no': None,
            'categories': 'cs.AI cs.LG',
            'license': 'http://creativecommons.org/licenses/by/4.0/',
            'abstract': 'This is a sample abstract for testing purposes. It discusses machine learning techniques and their applications in various domains.',
            'versions': [{'version': 'v1', 'created': 'Mon, 1 Jan 2024 10:00:00 GMT'}],
            'update_date': '2024-01-01',
            'authors_parsed': [['Smith', 'Alice', ''], ['Jones', 'Bob', '']],
            'author_ids': ['https://orcid.org/0000-0001-0001-0001', 'https://orcid.org/0000-0001-0001-0002'],
            'deleted': False,
            'citations': ['10.1234/cited.paper.001', '10.1234/cited.paper.002'],
            'citation_count': 5
        },
        {
            'id': '2024.12346',
            'submitter': 'Test Submitter 2',
            'authors': 'Carol Davis',
            'title': 'Another Sample Paper on Computer Vision',
            'comments': '10 pages, 5 figures',
            'journal-ref': None,
            'doi': '10.1234/test.paper.002',
            'report-no': None,
            'categories': 'cs.CV',
            'license': 'http://arxiv.org/licenses/nonexclusive-distrib/1.0/',
            'abstract': 'This paper presents novel approaches to computer vision problems, with experimental results on standard benchmarks.',
            'versions': [{'version': 'v1', 'created': 'Tue, 2 Jan 2024 12:00:00 GMT'}],
            'update_date': '2024-01-02',
            'authors_parsed': [['Davis', 'Carol', '']],
            'author_ids': ['https://orcid.org/0000-0001-0001-0003'],
            'deleted': False,
            'citations': ['10.1234/cited.paper.003'],
            'citation_count': 3
        },
        {
            'id': '2024.12347',
            'submitter': 'Test Submitter 3',
            'authors': 'David Lee, Emma Wilson',
            'title': 'Research on Natural Language Processing',
            'comments': None,
            'journal-ref': None,
            'doi': '10.1234/test.paper.003',
            'report-no': None,
            'categories': 'cs.CL',
            'license': 'http://creativecommons.org/licenses/by/4.0/',
            'abstract': 'An investigation into transformer models and their effectiveness in NLP tasks.',
            'versions': [{'version': 'v1', 'created': 'Wed, 3 Jan 2024 14:00:00 GMT'}],
            'update_date': '2024-01-03',
            'authors_parsed': [['Lee', 'David', ''], ['Wilson', 'Emma', '']],
            'author_ids': ['https://orcid.org/0000-0001-0001-0004', 'https://orcid.org/0000-0001-0001-0005'],
            'deleted': False,
            'citations': [],
            'citation_count': 0
        },
        {
            'id': '2024.12348',
            'submitter': 'Test Submitter 4',
            'authors': 'Frank Miller',
            'title': 'Deleted Paper Example',
            'comments': None,
            'journal-ref': None,
            'doi': '10.1234/test.paper.004',
            'report-no': None,
            'categories': 'cs.AI',
            'license': None,
            'abstract': 'This paper has been deleted.',
            'versions': [{'version': 'v1', 'created': 'Thu, 4 Jan 2024 16:00:00 GMT'}],
            'update_date': '2024-01-04',
            'authors_parsed': [['Miller', 'Frank', '']],
            'author_ids': ['https://orcid.org/0000-0001-0001-0006'],
            'deleted': True,
            'citations': [],
            'citation_count': 0
        },
        {
            'id': '2024.12349',
            'submitter': 'Test Submitter 5',
            'authors': 'Grace Taylor',
            'title': 'High Citation Count Paper',
            'comments': 'Best paper award',
            'journal-ref': 'Top Conference 2024',
            'doi': '10.1234/test.paper.005',
            'report-no': None,
            'categories': 'cs.AI cs.LG cs.CV',
            'license': 'http://creativecommons.org/licenses/by/4.0/',
            'abstract': 'A highly influential paper with many citations, demonstrating breakthrough results.',
            'versions': [{'version': 'v1', 'created': 'Fri, 5 Jan 2024 18:00:00 GMT'}],
            'update_date': '2024-01-05',
            'authors_parsed': [['Taylor', 'Grace', '']],
            'author_ids': ['https://orcid.org/0000-0001-0001-0007'],
            'deleted': False,
            'citations': ['10.1234/cited.paper.004', '10.1234/cited.paper.005', '10.1234/cited.paper.006'],
            'citation_count': 100
        }
    ]

    for paper in sample_papers:
        conn.execute("""
            INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            paper['id'], paper['submitter'], paper['authors'], paper['title'],
            paper['comments'], paper['journal-ref'], paper['doi'], paper['report-no'],
            paper['categories'], paper['license'], paper['abstract'], paper['versions'],
            paper['update_date'], paper['authors_parsed'], paper['author_ids'],
            paper['deleted'], paper['citations'], paper['citation_count']
        ])

    # Insert sample authors
    sample_authors = [
        {
            'author_id': 'https://orcid.org/0000-0001-0001-0001',
            'name': 'Alice Smith',
            'paper_dois': ['10.1234/test.paper.001'],
            'h_index': 15,
            'works_count': 50,
            'cited_by_count': 1200
        },
        {
            'author_id': 'https://orcid.org/0000-0001-0001-0002',
            'name': 'Bob Jones',
            'paper_dois': ['10.1234/test.paper.001'],
            'h_index': 12,
            'works_count': 40,
            'cited_by_count': 900
        },
        {
            'author_id': 'https://orcid.org/0000-0001-0001-0003',
            'name': 'Carol Davis',
            'paper_dois': ['10.1234/test.paper.002'],
            'h_index': 20,
            'works_count': 75,
            'cited_by_count': 2000
        },
        {
            'author_id': 'https://orcid.org/0000-0001-0001-0007',
            'name': 'Grace Taylor',
            'paper_dois': ['10.1234/test.paper.005'],
            'h_index': 35,
            'works_count': 100,
            'cited_by_count': 5000
        }
    ]

    for author in sample_authors:
        conn.execute("""
            INSERT INTO authors VALUES (?, ?, ?, ?, ?, ?)
        """, [
            author['author_id'], author['name'], author['paper_dois'],
            author['h_index'], author['works_count'], author['cited_by_count']
        ])

    conn.close()
    print(f"✅ Test database created at: {TEST_DB_PATH}")
    print(f"   - Papers: {len(sample_papers)}")
    print(f"   - Authors: {len(sample_authors)}")
    print(f"   - File size: {os.path.getsize(TEST_DB_PATH) / 1024:.2f} KB")


if __name__ == '__main__':
    create_test_database()
"""
Pytest configuration for ResearchViewer tests.

This module configures the test environment to use the test database
instead of the production database.
"""

import os
import sys

# CRITICAL: Set environment variables BEFORE any other imports
# Get the tests directory
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
TEST_DB_PATH = os.path.join(TESTS_DIR, 'test_data.db')

# Set environment variable for test database IMMEDIATELY
os.environ['DATABASE_PATH'] = TEST_DB_PATH
os.environ['TESTING'] = '1'

# Add project root to Python path
sys.path.insert(0, PROJECT_ROOT)

import pytest


def pytest_configure(config):
    """Configure pytest to use test database."""
    print(f"\n🧪 Using test database: {TEST_DB_PATH}")


def pytest_sessionstart(session):
    """Ensure test database exists before running tests."""
    if not os.path.exists(TEST_DB_PATH):
        print(f"\n❌ Test database not found at: {TEST_DB_PATH}")
        print("   Creating test database...")

        try:
            # Import and run the creation script
            sys.path.insert(0, TESTS_DIR)
            from create_test_db import create_test_database
            create_test_database()
            print("✅ Test database created successfully")
        except Exception as e:
            print(f"⚠️  Could not create test database: {e}")
            print("   Creating minimal test database...")
            # Create minimal database for tests to pass
            import duckdb
            db = duckdb.connect(TEST_DB_PATH)
            db.execute("CREATE TABLE IF NOT EXISTS papers (id VARCHAR PRIMARY KEY, title VARCHAR, citation_count INTEGER, categories VARCHAR, update_date DATE, deleted BOOLEAN, citations VARCHAR[], authors VARCHAR)")
            db.execute("CREATE TABLE IF NOT EXISTS authors (author_id VARCHAR PRIMARY KEY, name VARCHAR, h_index INTEGER, works_count INTEGER, cited_by_count INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS microtopics (microtopic_id VARCHAR PRIMARY KEY, label VARCHAR, bucket_value VARCHAR, size INTEGER)")
            db.close()
            print("✅ Minimal test database created")


@pytest.fixture(scope='session')
def test_db_path():
    """Return path to test database."""
    return TEST_DB_PATH
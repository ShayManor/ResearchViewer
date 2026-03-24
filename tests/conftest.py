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

# Set environment variables for test database IMMEDIATELY
# Point both user and data DB to the same test database
os.environ['DATABASE_PATH'] = TEST_DB_PATH  # Legacy
os.environ['USER_DB_PATH'] = TEST_DB_PATH   # User tables
os.environ['DATA_DB_PATH'] = TEST_DB_PATH   # Data tables (papers, authors, etc.)
os.environ['TESTING'] = '1'                 # Enable test mode (read-write for data DB)

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
            db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username VARCHAR, email VARCHAR, password_hash VARCHAR, firebase_uid VARCHAR)")
            db.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq START 1")
            db.close()
            print("✅ Minimal test database created")
    else:
        # Database exists, ensure it has firebase_uid column and sequences
        print(f"\n🔧 Checking test database schema...")
        import duckdb
        db = duckdb.connect(TEST_DB_PATH)

        try:
            # Check if firebase_uid column exists
            db.execute("SELECT firebase_uid FROM users LIMIT 1").fetchone()
        except:
            print("   Adding firebase_uid column to users table...")
            try:
                db.execute("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR")
                print("   ✅ Added firebase_uid column")
            except Exception as e:
                print(f"   ⚠️  Could not add firebase_uid column: {e}")

        try:
            # Check if users_id_seq exists
            db.execute("SELECT nextval('users_id_seq')").fetchone()
        except:
            print("   Creating users_id_seq sequence...")
            try:
                max_id = db.execute("SELECT COALESCE(MAX(id), 0) FROM users").fetchone()[0]
                db.execute(f"CREATE SEQUENCE users_id_seq START {max_id + 1}")
                print(f"   ✅ Created users_id_seq starting at {max_id + 1}")
            except Exception as e:
                print(f"   ⚠️  Could not create sequence: {e}")

        db.close()


@pytest.fixture(scope='session')
def test_db_path():
    """Return path to test database."""
    return TEST_DB_PATH
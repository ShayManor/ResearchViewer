"""
Pytest configuration for ResearchViewer tests.

This module configures the test environment to use the test database
instead of the production database.
"""

import os
import sys
import pytest

# Get the tests directory
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
TEST_DB_PATH = os.path.join(TESTS_DIR, 'test_data.db')

# Add project root to Python path
sys.path.insert(0, PROJECT_ROOT)


def pytest_configure(config):
    """Configure pytest to use test database."""
    # Set environment variable for test database
    os.environ['DATABASE_PATH'] = TEST_DB_PATH
    print(f"\n🧪 Using test database: {TEST_DB_PATH}")


def pytest_sessionstart(session):
    """Ensure test database exists before running tests."""
    if not os.path.exists(TEST_DB_PATH):
        print(f"\n❌ Test database not found at: {TEST_DB_PATH}")
        print("   Creating test database...")

        # Import and run the creation script
        sys.path.insert(0, TESTS_DIR)
        from create_test_db import create_test_database
        create_test_database()

        print("✅ Test database created successfully")


@pytest.fixture(scope='session')
def test_db_path():
    """Return path to test database."""
    return TEST_DB_PATH
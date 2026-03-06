"""Database connection management for DuckDB."""

import duckdb
import os
import numpy as np
import pandas as pd
from typing import Optional, Any

DATABASE_PATH = os.getenv(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.db')
)

_connection: Optional[duckdb.DuckDBPyConnection] = None


def get_db() -> duckdb.DuckDBPyConnection:
    """Get singleton database connection."""
    global _connection
    if _connection is None:
        # DuckDB supports both file paths and URLs
        _connection = duckdb.connect(DATABASE_PATH, read_only=False)
    return _connection


def init_app(app):
    """Initialize database connection on app startup.

    Args:
        app: Flask application instance
    """
    # Log database path for debugging in containers
    app.logger.info(f"DuckDB path configured: {DATABASE_PATH}")

    # Connection will be created lazily on first use
    # This allows tests to import the module without locking the database


def close_db():
    """Close database connection (for graceful shutdown)."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def get_schema() -> dict:
    """Get database schema for documentation/validation.

    Returns:
        dict: Dictionary mapping table names to their column schemas
    """
    db = get_db()
    tables = db.execute("SHOW TABLES").fetchall()
    schema = {}
    for (table_name,) in tables:
        columns = db.execute(f"DESCRIBE {table_name}").fetchall()
        schema[table_name] = columns
    return schema


def df_to_json_serializable(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to JSON-serializable list of dicts."""
    def convert_value(val):
        """Convert a value to JSON-serializable format."""
        # Check for arrays/lists first (before pd.isna which fails on arrays)
        if isinstance(val, (np.ndarray, list)):
            # Convert arrays to lists, handling nested arrays
            return [convert_value(v) for v in val] if len(val) > 0 else []
        elif val is None or (not isinstance(val, (list, dict)) and pd.isna(val)):
            return None
        elif isinstance(val, (np.integer, np.int64)):
            return int(val)
        elif isinstance(val, (np.floating, np.float64)):
            return float(val)
        elif isinstance(val, (np.bool_, bool)):
            return bool(val)
        elif isinstance(val, dict):
            return {k: convert_value(v) for k, v in val.items()}
        else:
            return val

    records = []
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            record[col] = convert_value(row[col])
        records.append(record)

    return records
"""Database connection management for DuckDB.

Dual database architecture:
- User DB: Read/write database for user data (users, reading lists, etc.)
- Data DB: Read-only database for research papers and microtopics
"""

import os
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from flask import g, has_app_context

# User database - read/write (users, reading lists, publications, read history)
USER_DB_PATH = os.getenv(
    "USER_DB_PATH",
    os.path.join(os.path.dirname(__file__), "user.db"),
)

# Data database - read-only (papers, microtopics, authors)
DATA_DB_PATH = os.getenv(
    "DATA_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data.db"),
)


def get_user_db() -> duckdb.DuckDBPyConnection:
    """Return read/write connection to user database (per Flask request)."""
    db = g.get("user_db")
    if db is None:
        db = duckdb.connect(USER_DB_PATH, read_only=False)
        g.user_db = db
    return db


def get_data_db() -> duckdb.DuckDBPyConnection:
    """Return read-only connection to data database (per Flask request)."""
    db = g.get("data_db")
    if db is None:
        # In test mode, allow writes to the data database
        # In production, enforce read-only mode for data integrity
        is_testing = os.getenv('TESTING') == '1'
        db = duckdb.connect(DATA_DB_PATH, read_only=(not is_testing))
        g.data_db = db
    return db


# Backward compatibility - defaults to data DB
def get_db() -> duckdb.DuckDBPyConnection:
    """Legacy method - defaults to data DB for backward compatibility."""
    return get_data_db()


def close_db(_exc: Exception | None = None) -> None:
    """Close all request-local connections if they exist."""
    if not has_app_context():
        return

    user_db = g.pop("user_db", None)
    if user_db is not None:
        user_db.close()

    data_db = g.pop("data_db", None)
    if data_db is not None:
        data_db.close()


def init_app(app) -> None:
    """Register DB teardown with Flask."""
    app.logger.info(f"User DB path configured: {USER_DB_PATH}")
    app.logger.info(f"Data DB path configured: {DATA_DB_PATH} (read-only)")
    app.teardown_appcontext(close_db)


def get_schema(db_type: str = 'both') -> dict:
    """Get database schema for documentation/validation.

    Args:
        db_type: 'user', 'data', or 'both' (default)
    """
    schema = {}

    if db_type in ('user', 'both'):
        with duckdb.connect(USER_DB_PATH, read_only=False) as db:
            tables = db.execute("SHOW TABLES").fetchall()
            for (table_name,) in tables:
                columns = db.execute(f"DESCRIBE {table_name}").fetchall()
                schema[f"user.{table_name}"] = columns

    if db_type in ('data', 'both'):
        with duckdb.connect(DATA_DB_PATH, read_only=True) as db:
            tables = db.execute("SHOW TABLES").fetchall()
            for (table_name,) in tables:
                columns = db.execute(f"DESCRIBE {table_name}").fetchall()
                schema[f"data.{table_name}"] = columns

    return schema


def df_to_json_serializable(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to JSON-serializable list of dicts."""
    def convert_value(val):
        if isinstance(val, (np.ndarray, list)):
            return [convert_value(v) for v in val] if len(val) > 0 else []
        elif val is None or (not isinstance(val, (list, dict)) and pd.isna(val)):
            return None
        elif isinstance(val, (np.integer, np.int64)):
            return int(val)
        elif isinstance(val, (np.floating, np.float64)):
            return float(val)
        elif isinstance(val, (np.bool_, bool)):
            return bool(val)
        elif isinstance(val, (pd.Timestamp, np.datetime64)):
            # Convert datetime to ISO format string (YYYY-MM-DD)
            return pd.Timestamp(val).strftime('%Y-%m-%d')
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
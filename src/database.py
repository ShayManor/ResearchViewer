"""Database connection management for DuckDB."""

import os
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from flask import g, has_app_context

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "data.db"),
)


def get_db() -> duckdb.DuckDBPyConnection:
    """Return one DuckDB connection per Flask request/app context."""
    db = g.get("db")
    if db is None:
        db = duckdb.connect(DATABASE_PATH, read_only=False)
        g.db = db
    return db


def close_db(_exc: Exception | None = None) -> None:
    """Close the request-local connection if one exists."""
    if not has_app_context():
        return

    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app) -> None:
    """Register DB teardown with Flask."""
    app.logger.info(f"DuckDB path configured: {DATABASE_PATH}")
    app.teardown_appcontext(close_db)


def get_schema() -> dict:
    """Get database schema for documentation/validation."""
    with duckdb.connect(DATABASE_PATH, read_only=False) as db:
        tables = db.execute("SHOW TABLES").fetchall()
        schema = {}
        for (table_name,) in tables:
            columns = db.execute(f"DESCRIBE {table_name}").fetchall()
            schema[table_name] = columns
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
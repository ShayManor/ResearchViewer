import argparse
import itertools
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import duckdb
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm


DB_PATH_DEFAULT = "../src/data.db"
WORKS_URL = "https://api.openalex.org/works"
MAX_DOIS_PER_REQUEST = 100
DEFAULT_RPS = 9.0
DEFAULT_WORKERS = 8
DEFAULT_FLUSH_ROWS = 5000

_tls = threading.local()
_rate_lock = threading.Lock()
_last_request_ts = 0.0


SAMPLE_DOIS = [
    "10.48550/arxiv.0712.3220",
    "10.1103/physrevd.78.023501",
    "10.48550/arxiv.0712.3225",
    "10.48550/arxiv.0712.3227",
    "10.1086/529016",
    "10.1007/s00220-008-0603-5",
]


def normalize_doi(raw: str | None) -> str | None:
    if raw is None:
        return None
    doi = raw.strip().lower()
    if not doi:
        return None
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:")
    doi = doi.rstrip(",")
    return doi or None


def doi_to_filter_value(doi: str) -> str:
    return doi


def get_session() -> requests.Session:
    if not hasattr(_tls, "session"):
        s = requests.Session()
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=0)
        s.mount("https://", adapter)
        s.headers.update({
            "User-Agent": "ResearchViewer OpenAlex topic backfill (mailto:shay.manor@gmail.edu)"
        })
        _tls.session = s
    return _tls.session


def rate_limit(max_rps: float) -> None:
    global _last_request_ts
    min_gap = 1.0 / max_rps
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_ts
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)
        _last_request_ts = time.time()


def compact_topic(topic: dict | None) -> dict | None:
    if not topic:
        return None
    return {
        "id": topic.get("id"),
        "display_name": topic.get("display_name"),
        "score": topic.get("score"),
        "subfield": topic.get("subfield"),
        "field": topic.get("field"),
        "domain": topic.get("domain"),
    }


def fetch_topic_batch(dois: list[str], *, mailto: str, max_rps: float) -> tuple[bool, dict[str, dict]]:
    """
    Returns (success, mapping keyed by normalized DOI).
    Missing matches are returned as empty dicts when the API request succeeded
    but OpenAlex had no matching work for that DOI.
    """
    out = {doi: {} for doi in dois}
    if not dois:
        return True, out

    filter_str = "doi:" + "|".join(doi_to_filter_value(d) for d in dois)
    params = {
        "filter": filter_str,
        "per-page": len(dois),
        "select": "id,doi,primary_topic,topics",
        "mailto": mailto,
    }

    last_exc = None
    for attempt in range(5):
        try:
            rate_limit(max_rps)
            r = get_session().get(WORKS_URL, params=params, timeout=30)

            if r.status_code == 429:
                time.sleep(min(30, 2 ** attempt))
                print(r.text)
                continue
            if r.status_code >= 500:
                time.sleep(min(30, 2 ** attempt))
                continue
            if r.status_code == 400:
                raise RuntimeError(f"OpenAlex 400 for batch starting with {dois[:3]}: {r.text[:500]}")

            r.raise_for_status()
            payload = r.json()
            for work in payload.get("results", []):
                returned_doi = normalize_doi(work.get("doi"))
                if not returned_doi:
                    continue
                primary = compact_topic(work.get("primary_topic"))
                topics = [compact_topic(t) for t in (work.get("topics") or []) if t]
                out[returned_doi] = {
                    "oa_work_id": work.get("id"),
                    "doi": returned_doi,
                    "primary_topic": primary,
                    "topics": topics,
                }
            return True, out
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(min(30, 2 ** attempt))

    if last_exc is not None:
        print(f"Failed batch after retries ({dois[:3]}...): {last_exc}")
    return False, out


def ensure_columns(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS oa_work_id VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_topic_id VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_topic_name VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_topic_score DOUBLE;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_subfield_id VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_subfield_name VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_field_id VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_field_name VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_domain_id VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS primary_domain_name VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS topics_json VARCHAR;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS topics_fetched BOOLEAN;")
    conn.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS topics_updated_at TIMESTAMP;")


def make_update_row(doi: str, record: dict, now_sql: str) -> tuple:
    primary = (record or {}).get("primary_topic") or {}
    subfield = primary.get("subfield") or {}
    field = primary.get("field") or {}
    domain = primary.get("domain") or {}
    topics_json = json.dumps(record.get("topics") or [], ensure_ascii=False)

    fetched = bool(record)

    return (
        (record or {}).get("oa_work_id"),
        primary.get("id"),
        primary.get("display_name"),
        primary.get("score"),
        subfield.get("id"),
        subfield.get("display_name"),
        field.get("id"),
        field.get("display_name"),
        domain.get("id"),
        domain.get("display_name"),
        topics_json,
        fetched,
        now_sql,
        doi,
    )


def flush_rows(conn: duckdb.DuckDBPyConnection, rows: list[tuple]) -> None:
    if not rows:
        return

    conn.executemany(
        """
        INSERT INTO topic_updates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    conn.execute(
        """
        UPDATE papers AS p
        SET
            oa_work_id = u.oa_work_id,
            primary_topic_id = u.primary_topic_id,
            primary_topic_name = u.primary_topic_name,
            primary_topic_score = u.primary_topic_score,
            primary_subfield_id = u.primary_subfield_id,
            primary_subfield_name = u.primary_subfield_name,
            primary_field_id = u.primary_field_id,
            primary_field_name = u.primary_field_name,
            primary_domain_id = u.primary_domain_id,
            primary_domain_name = u.primary_domain_name,
            topics_json = u.topics_json,
            topics_fetched = u.topics_fetched,
            topics_updated_at = u.topics_updated_at
        FROM topic_updates AS u
        WHERE lower(p.doi) = u.doi_lc;
        """
    )
    conn.execute("DELETE FROM topic_updates")


def batched(iterable: Iterable[str], n: int):
    iterator = iter(iterable)
    while True:
        batch = list(itertools.islice(iterator, n))
        if not batch:
            return
        yield batch


def select_target_dois(conn: duckdb.DuckDBPyConnection, *, force: bool) -> list[str]:
    where_extra = "" if force else "AND topics_fetched IS NULL"
    rows = conn.execute(
        f"""
        SELECT DISTINCT lower(doi) AS doi_lc
        FROM papers
        WHERE deleted IS NOT TRUE
          AND doi IS NOT NULL
          AND trim(doi) <> ''
          {where_extra}
        ORDER BY doi_lc;
        """
    ).fetchall()
    return [normalize_doi(r[0]) for r in rows if normalize_doi(r[0])]


def run_demo(dois: list[str], *, mailto: str, max_rps: float) -> None:
    cleaned = [normalize_doi(d) for d in dois if normalize_doi(d)]
    success, out = fetch_topic_batch(cleaned, mailto=mailto, max_rps=max_rps)
    print(json.dumps({"success": success, "results": out}, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk backfill OpenAlex topic hierarchy into DuckDB papers table.")
    parser.add_argument("--db", default=DB_PATH_DEFAULT)
    parser.add_argument("--mailto", default="manors@purdue.edu")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--flush-rows", type=int, default=DEFAULT_FLUSH_ROWS)
    parser.add_argument("--max-rps", type=float, default=DEFAULT_RPS)
    parser.add_argument("--force", action="store_true", help="Re-fetch papers even if topics_fetched is already set.")
    parser.add_argument("--demo", action="store_true", help="Only query the sample DOIs and print JSON; do not touch the DB.")
    parser.add_argument("--doi", action="append", default=[], help="Extra DOI(s) to query in --demo mode.")
    args = parser.parse_args()

    if args.batch_size < 1 or args.batch_size > MAX_DOIS_PER_REQUEST:
        raise ValueError(f"--batch-size must be between 1 and {MAX_DOIS_PER_REQUEST}")

    if args.demo:
        demo_dois = SAMPLE_DOIS + args.doi
        run_demo(demo_dois, mailto=args.mailto, max_rps=args.max_rps)
        return

    conn = duckdb.connect(args.db)
    ensure_columns(conn)
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS topic_updates (
            oa_work_id VARCHAR,
            primary_topic_id VARCHAR,
            primary_topic_name VARCHAR,
            primary_topic_score DOUBLE,
            primary_subfield_id VARCHAR,
            primary_subfield_name VARCHAR,
            primary_field_id VARCHAR,
            primary_field_name VARCHAR,
            primary_domain_id VARCHAR,
            primary_domain_name VARCHAR,
            topics_json VARCHAR,
            topics_fetched BOOLEAN,
            topics_updated_at TIMESTAMP,
            doi_lc VARCHAR
        );
        """
    )

    target_dois = select_target_dois(conn, force=args.force)
    total = len(target_dois)
    print(f"Target papers with DOI to classify: {total}")
    if total == 0:
        conn.close()
        return

    batch_iter = batched(target_dois, args.batch_size)
    pending_rows: list[tuple] = []
    finished = 0

    def job(batch: list[str]) -> tuple[bool, dict[str, dict]]:
        return fetch_topic_batch(batch, mailto=args.mailto, max_rps=args.max_rps)

    try:
        with tqdm(total=total) as pbar:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futures = []
                for _ in range(min(args.workers, (total + args.batch_size - 1) // args.batch_size)):
                    try:
                        futures.append(ex.submit(job, next(batch_iter)))
                    except StopIteration:
                        break

                while futures:
                    for f in as_completed(futures):
                        futures.remove(f)
                        success, result = f.result()
                        batch_processed = len(result)
                        if success:
                            now_sql = time.strftime("%Y-%m-%d %H:%M:%S")
                            for doi, record in result.items():
                                pending_rows.append(make_update_row(doi, record, now_sql))
                        finished += batch_processed
                        pbar.update(batch_processed)

                        if len(pending_rows) >= args.flush_rows:
                            flush_rows(conn, pending_rows)
                            pending_rows = []

                        try:
                            futures.append(ex.submit(job, next(batch_iter)))
                        except StopIteration:
                            pass
                        break

        if pending_rows:
            flush_rows(conn, pending_rows)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

import threading
import itertools
import time

import duckdb
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

conn = duckdb.connect("../data.db")

# Add columns for extra data if not exist
conn.execute("""
    ALTER TABLE authors ADD COLUMN IF NOT EXISTS works_count INTEGER;
""")
conn.execute("""
    ALTER TABLE authors ADD COLUMN IF NOT EXISTS cited_by_count INTEGER;
""")

# Get authors without names
res = conn.execute("""
    SELECT author_id FROM authors 
    WHERE name IS NULL AND author_id IS NOT NULL
""").fetchall()

total_authors = [r[0] for r in res]

# Separate by source
openalex_ids = [a for a in total_authors if "openalex.org" in a]
orcid_ids = [a for a in total_authors if "orcid.org" in a]

print(f"OpenAlex: {len(openalex_ids)}, ORCID: {len(orcid_ids)}")

_tls = threading.local()


def get_session():
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=32, pool_maxsize=32))
        _tls.s = s
    return _tls.s


def get_openalex_batch(urls: list[str]) -> dict[str, dict]:
    """
    Batch query OpenAlex for author info.
    Returns {url: {name, works_count, cited_by_count, h_index}}
    """
    out = {u: {} for u in urls}

    # Extract IDs: https://openalex.org/A5025817570 -> A5025817570
    ids = [u.rstrip("/").split("/")[-1] for u in urls]
    id_to_url = {u.rstrip("/").split("/")[-1]: u for u in urls}

    id_filter = "|".join(ids)

    try:
        r = get_session().get(
            "https://api.openalex.org/authors",
            params={
                "filter": f"ids.openalex:{id_filter}",
                "select": "id,display_name,works_count,cited_by_count,summary_stats",
                "per_page": 50,
            },
            timeout=30,
        )

        if not r.ok:
            return out

        for author in r.json().get("results", []):
            author_id = author.get("id", "").replace("https://openalex.org/", "")
            url = id_to_url.get(author_id)
            if url:
                out[url] = {
                    "name": author.get("display_name"),
                    "works_count": author.get("works_count"),
                    "cited_by_count": author.get("cited_by_count"),
                    "h_index": (author.get("summary_stats") or {}).get("h_index"),
                }
    except requests.RequestException as e:
        print(f"OpenAlex error: {e}")

    return out


def get_orcid_single(url: str) -> dict:
    """Get author info from ORCID."""
    try:
        orcid_id = url.rstrip("/").split("/")[-1]
        r = get_session().get(
            f"https://pub.orcid.org/v3.0/{orcid_id}/person",
            headers={"Accept": "application/json"},
            timeout=10,
        )

        if r.ok:
            data = r.json()
            name_data = data.get("name")
            if name_data:
                given = (name_data.get("given-names") or {}).get("value", "")
                family = (name_data.get("family-name") or {}).get("value", "")
                name = f"{given} {family}".strip()
                if name:
                    return {"name": name}
    except requests.RequestException:
        pass

    return {}


# Rate limiting for ORCID (no batch API)
_rate_lock = threading.Lock()
_last_orcid = 0.0


def rate_limited_orcid(url):
    global _last_orcid
    with _rate_lock:
        elapsed = time.time() - _last_orcid
        if elapsed < 0.1:  # 10 RPS max
            time.sleep(0.1 - elapsed)
        _last_orcid = time.time()
    return url, get_orcid_single(url)


# Process OpenAlex (fast, batched)
BATCH_SIZE = 50
DB_FLUSH = 2000
MAX_WORKERS = 10

pending_rows = []


def flush_to_db():
    global pending_rows
    if not pending_rows:
        return

    conn.executemany(
        """
        UPDATE authors 
        SET name = ?, works_count = ?, cited_by_count = ?, h_index = ?
        WHERE author_id = ?
    """,
        pending_rows,
    )
    conn.commit()
    pending_rows = []


print("Processing OpenAlex authors...")
with tqdm(total=len(openalex_ids)) as pbar:
    for batch in itertools.batched(openalex_ids, BATCH_SIZE):
        results = get_openalex_batch(list(batch))

        for url, data in results.items():
            if data.get("name"):
                pending_rows.append(
                    (
                        data.get("name"),
                        data.get("works_count"),
                        data.get("cited_by_count"),
                        data.get("h_index"),
                        url,
                    )
                )

        pbar.update(len(batch))

        if len(pending_rows) >= DB_FLUSH:
            flush_to_db()

flush_to_db()


# Process ORCID (slower, individual requests with threading)
print("Processing ORCID authors...")
with tqdm(total=len(orcid_ids)) as pbar:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(rate_limited_orcid, url): url for url in orcid_ids}

        for f in as_completed(futures):
            url, data = f.result()
            if data.get("name"):
                pending_rows.append(
                    (
                        data.get("name"),
                        None,  # ORCID doesn't give works_count
                        None,
                        None,
                        url,
                    )
                )

            pbar.update(1)

            if len(pending_rows) >= DB_FLUSH:
                flush_to_db()

flush_to_db()

conn.close()
print("Done")

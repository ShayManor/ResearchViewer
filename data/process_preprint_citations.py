# OpenAlex does not handle preprint citations so this script uses semantic scholars to finish dataset (800k records)
# Run after process_citations (much slower due to rate limits)
import os
import time
import threading
import itertools

import duckdb
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

conn = duckdb.connect("../data.db")

# Get papers with empty citations from OpenAlex (arxiv papers)
res = conn.execute("""
    SELECT doi FROM papers 
    WHERE (citations IS NULL OR array_length(citations) = 0)
    AND deleted = false AND doi IS NOT NULL
""").fetchdf()
total_dois = [x[0] for x in res.values]
count = len(total_dois)
print(f"Count: {count}")

_tls = threading.local()


def get_session():
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=32, pool_maxsize=32))
        _tls.s = s
    return _tls.s


def doi_to_s2_id(doi: str) -> str:
    """Convert DOI to Semantic Scholar paper ID format."""
    doi = doi.strip().lower()
    # Convert arxiv DOIs to ARXIV: format (much better coverage)
    if doi.startswith("10.48550/arxiv."):
        arxiv_id = doi.removeprefix("10.48550/arxiv.")
        return f"ARXIV:{arxiv_id}"
    return f"DOI:{doi}"


def get_citations_batch(dois: list[str], token: str | None = None) -> dict[str, list[str]]:
    """
    Batch query Semantic Scholar for references (outgoing citations).
    Returns {doi: [list of cited DOIs]}
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/batch"

    # Convert DOIs to S2 format
    paper_ids = [doi_to_s2_id(d) for d in dois]

    headers = {"Content-Type": "application/json"}
    if token:
        headers["x-api-key"] = token

    for attempt in range(3):
        try:
            r = get_session().post(
                url,
                headers=headers,
                json={"ids": paper_ids},
                params={"fields": "externalIds,references.externalIds"},
                timeout=60,
            )

            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 400:
                return {d.lower(): [] for d in dois}

            r.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt == 2:
                print(f"Failed batch: {e}")
                return {d.lower(): [] for d in dois}
            time.sleep(1)
    else:
        return {d.lower(): [] for d in dois}

    # Parse results
    results = r.json()
    out = {d.lower(): [] for d in dois}

    for i, paper in enumerate(results):
        if paper is None:
            continue

        # Get the original DOI for this paper
        original_doi = dois[i].lower()

        refs = paper.get("references") or []
        cited_dois = []
        for ref in refs:
            if ref is None:
                continue
            ext_ids = ref.get("externalIds") or {}
            # Prefer DOI, fall back to ArXiv
            if ext_ids.get("DOI"):
                cited_dois.append(ext_ids["DOI"].lower())
            elif ext_ids.get("ArXiv"):
                cited_dois.append(f"10.48550/arxiv.{ext_ids['ArXiv'].lower()}")

        out[original_doi] = cited_dois

    return out


# Rate limit: 1 RPS with API key
_rate_lock = threading.Lock()
_last_request = 0.0


def rate_limited_job(batch, token):
    global _last_request
    with _rate_lock:
        elapsed = time.time() - _last_request
        if elapsed < 1.0:  # 1 RPS with API key
            time.sleep(1.0 - elapsed)
        _last_request = time.time()
    return get_citations_batch(list(batch), token)


MAX_WORKERS = 4  # Keep low due to 1 RPS limit
BATCH_SIZE = 500  # S2 allows up to 500 per request
DB_FLUSH = 5000

token = os.getenv("S2_API_KEY")  # Get free key from semanticscholar.org/product/api
if not token:
    print("Warning: No S2_API_KEY set. Using shared rate limit (slower).")

conn.execute("CREATE TEMP TABLE IF NOT EXISTS citation_updates (doi_lc VARCHAR, citations VARCHAR[]);")

batch_iter = itertools.batched(total_dois, BATCH_SIZE)
pending_rows = []

with tqdm(total=count) as pbar:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        for _ in range(MAX_WORKERS):
            try:
                futures.append(ex.submit(rate_limited_job, next(batch_iter), token))
            except StopIteration:
                break

        while futures:
            for f in as_completed(futures):
                out = f.result()
                pending_rows.extend([(doi, cites) for doi, cites in out.items()])
                pbar.update(len(out))

                if len(pending_rows) >= DB_FLUSH:
                    conn.executemany("INSERT INTO citation_updates VALUES (?, ?)", pending_rows)
                    conn.execute("""
                        UPDATE papers SET citations = u.citations
                        FROM citation_updates u WHERE lower(papers.doi) = u.doi_lc;
                    """)
                    conn.execute("DELETE FROM citation_updates")
                    conn.commit()
                    pending_rows = []

                futures.remove(f)
                try:
                    futures.append(ex.submit(rate_limited_job, next(batch_iter), token))
                except StopIteration:
                    pass

    if pending_rows:
        conn.executemany("INSERT INTO citation_updates VALUES (?, ?)", pending_rows)
        conn.execute("""
            UPDATE papers SET citations = u.citations
            FROM citation_updates u WHERE lower(papers.doi) = u.doi_lc;
        """)
        conn.commit()

conn.close()
print("Done")
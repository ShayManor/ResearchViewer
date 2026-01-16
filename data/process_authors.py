import itertools
import time

import duckdb
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

import threading
from requests.adapters import HTTPAdapter

# 1) Get DOI for all papers from arxiv id
# 2) Get author list and update papers table
# 3) Get citations list from DOIs (of DOIs) and update papers table

conn = duckdb.connect("../data.db")
# Fix missing doi from arxiv ID
res = conn.execute(
    "UPDATE papers SET doi = '10.48550/arXiv.' || id WHERE doi IS NULL AND id IS NOT NULL;"
)

res = conn.execute("SELECT doi FROM papers where author_ids is null;").fetchdf()
count = (
    conn.execute("SELECT count(*) from papers where author_ids is null;")
    .fetchdf()
    .values
)[0][0]

_tls = threading.local()

def get_session():
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=32, pool_maxsize=32))
        _tls.s = s
    return _tls.s


def get_author_ids(dois: str, *, prefer_orcid: bool = True) -> dict[str, list[str]]:
    """
    Returns an id for each author on each paper (doi)
    - If prefer_orcid=True and ORCID exists, returns ORCID URL for that author
    - Otherwise returns OpenAlex Author ID
    """
    url = "https://api.openalex.org/works"

    filter_str = "doi:" + "|".join([f"https://doi.org/{d.split()[0].rstrip(',')}" for d in dois if d and d.strip()])
    for attempt in range(3):
        try:
            r = get_session().get(
                url,
                params={
                    "filter": filter_str,
                    "per-page": 50,
                    "select": "doi,authorships",
                    "mailto": "manors@purdue.edu",
                },
                timeout=20,
            )
            if r.status_code == 400:
                print(f"Skipping bad batch: {dois[:2]}...")
                return {}
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue

            r.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt == 2:
                print(f"Failed batch after 3 attempts: {e}")
                return {}
            time.sleep(1)

    out: dict[str, list[str]] = {}

    works = r.json()["results"]
    for work in works:
        work_doi = work["doi"].removeprefix("https://doi.org/").lower()
        if not work_doi:
            raise ValueError("Doi not found")
        ids: list[str] = []
        for a in work.get("authorships", []):
            author = a.get("author", {}) or {}
            openalex_id = author.get("id")  # unique author id
            orcid = author.get("orcid")  # may be None

            if prefer_orcid and orcid:
                ids.append(orcid)
            elif openalex_id:
                ids.append(openalex_id)
        out[work_doi] = ids

    return out


total_dois = [x[0] for x in res.values]

print(f"Count: {count}")
MAX_WORKERS = 16

idx = 0
BATCHES_TO_SAVE = 200
conn.execute("CREATE TEMP TABLE IF NOT EXISTS batch_updates (doi_lc VARCHAR, author_ids VARCHAR[]);")
conn.execute("BEGIN TRANSACTION;")

def job(sub):
    return get_author_ids(sub)
batch_iter = itertools.batched(total_dois, 50)

with tqdm(total=count) as pbar:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(job, next(batch_iter)) for _ in range(MAX_WORKERS)]
        finished = 0
        pending_rows = []  # accumulate rows
        while futures:
            for f in as_completed(futures):
                out = f.result()
                pending_rows.extend([(doi, ids) for doi, ids in out.items()])
                finished += 50
                pbar.update(50)

                # Bulk write every BATCHES_TO_SAVE batches
                if finished % (BATCHES_TO_SAVE * 50) == 0 and pending_rows:
                    conn.executemany("INSERT INTO batch_updates VALUES (?, ?)", pending_rows)
                    conn.execute("""
                                UPDATE papers
                                SET author_ids = u.author_ids
                                FROM batch_updates u
                                WHERE lower(papers.doi) = u.doi_lc;
                            """)
                    conn.execute("DELETE FROM batch_updates")
                    conn.commit()
                    pending_rows = []

                # refill
                try:
                    futures.remove(f)
                    futures.append(ex.submit(job, next(batch_iter)))
                except StopIteration:
                    # futures.remove(f)
                    pass
        # Flush remaining
        if pending_rows:
            conn.executemany("INSERT INTO batch_updates VALUES (?, ?)", pending_rows)
            conn.execute("""
                        UPDATE papers SET author_ids = u.author_ids
                        FROM batch_updates u WHERE lower(papers.doi) = u.doi_lc;
                    """)
            conn.execute("DELETE FROM batch_updates")

conn.execute("COMMIT;")

null_count = conn.execute(
    "select count(*) from papers where author_ids is null;"
).fetchdf()
print(null_count.values)
conn.close()

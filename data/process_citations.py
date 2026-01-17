import itertools
import time
import threading

import duckdb
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

conn = duckdb.connect("data.db")

res = conn.execute("SELECT doi FROM papers WHERE citations IS NULL AND deleted = false AND doi IS NOT NULL;").fetchdf()
total_dois = [x[0] for x in res.values]
count = len(total_dois)
print(f"Count: {count}")

_tls = threading.local()

def get_session():
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=64, pool_maxsize=64))
        _tls.s = s
    return _tls.s


def get_citations_batch(dois: list[str]) -> dict[str, list[str]]:
    """Returns {doi: [list of OpenAlex work IDs cited]}"""
    url = "https://api.openalex.org/works"
    filter_str = "doi:" + "|".join([f"https://doi.org/{d.split()[0].rstrip(',')}" for d in dois if d and d.strip()])

    for attempt in range(3):
        try:
            r = get_session().get(
                url,
                params={
                    "filter": filter_str,
                    "per-page": 50,
                    "select": "doi,referenced_works",
                    "mailto": "manors@purdue.edu",
                },
                timeout=30,
            )
            if r.status_code == 400:
                return {d.lower(): [] for d in dois}
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if attempt == 2:
                return {d.lower(): [] for d in dois}
            time.sleep(1)
    else:
        return {d.lower(): [] for d in dois}

    out = {d.split()[0].rstrip(',').lower(): [] for d in dois}

    for work in r.json()["results"]:
        work_doi = work.get("doi", "")
        if not work_doi:
            continue
        work_doi = work_doi.removeprefix("https://doi.org/").lower()
        # referenced_works is a list of OpenAlex IDs like "https://openalex.org/W2741809807"
        refs = work.get("referenced_works") or []
        # Strip prefix to just get the ID
        out[work_doi] = [r.removeprefix("https://openalex.org/") for r in refs]

    return out


MAX_WORKERS = 16
BATCHES_TO_SAVE = 200

conn.execute("CREATE TEMP TABLE IF NOT EXISTS citation_updates (doi_lc VARCHAR, cited_work_ids VARCHAR[]);")

def job(batch):
    return get_citations_batch(list(batch))

batch_iter = itertools.batched(total_dois, 50)

with tqdm(total=count) as pbar:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        for _ in range(MAX_WORKERS):
            try:
                futures.append(ex.submit(job, next(batch_iter)))
            except StopIteration:
                break

        pending_rows = []
        while futures:
            for f in as_completed(futures):
                out = f.result()
                pending_rows.extend([(doi, ids) for doi, ids in out.items()])
                pbar.update(len(out))

                if len(pending_rows) >= BATCHES_TO_SAVE * 50:
                    conn.executemany("INSERT INTO citation_updates VALUES (?, ?)", pending_rows)
                    conn.execute("""
                        UPDATE papers SET citations = u.cited_work_ids
                        FROM citation_updates u WHERE lower(papers.doi) = u.doi_lc;
                    """)
                    conn.execute("DELETE FROM citation_updates")
                    conn.commit()
                    pending_rows = []

                futures.remove(f)
                try:
                    futures.append(ex.submit(job, next(batch_iter)))
                except StopIteration:
                    pass

    if pending_rows:
        conn.executemany("INSERT INTO citation_updates VALUES (?, ?)", pending_rows)
        conn.execute("""
            UPDATE papers SET citations = u.cited_work_ids
            FROM citation_updates u WHERE lower(papers.doi) = u.doi_lc;
        """)
        conn.commit()

conn.close()
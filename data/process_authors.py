import itertools

import duckdb
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

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
)


def get_author_ids(dois: str, *, prefer_orcid: bool = True) -> dict[str, list[str]]:
    """
    Returns an id for each author on each paper (doi)
    - If prefer_orcid=True and ORCID exists, returns ORCID URL for that author
    - Otherwise returns OpenAlex Author ID
    """
    url = "https://api.openalex.org/works"

    filter_str = "doi:" + "|".join([f"https://doi.org/{d.split()[0]}" for d in dois])
    session = requests.Session()
    r = session.get(
        url,
        params={
            "filter": filter_str,
            "per-page": 50,
            "select": "doi,authorships",
            "mailto": "manors@purdue.edu",
        },
        timeout=20,
    )

    r.raise_for_status()
    w = r.json()["results"]
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

print(f"Count: {count[0]}")
batches_per_commit = 2000

idx = 0
conn.execute("BEGIN TRANSACTION;")

with tqdm(total=count[0][0]) as pbar:
    for sub_dois in itertools.batched(total_dois, 50):
        author_ids = get_author_ids(sub_dois)
        updates = [(author_list, doi) for doi, author_list in author_ids.items()]

        conn.executemany(
            "UPDATE papers SET author_ids = ? WHERE doi = ?", updates
        )
        pbar.update(50)
        idx += 50

        if idx % batches_per_commit == 0:
            conn.execute("COMMIT;")
            conn.execute("BEGIN TRANSACTION;")

conn.execute("COMMIT;")

null_count = conn.execute(
    "select count(*) from papers where author_ids is null;"
).fetchdf()
print(null_count.values)
conn.close()

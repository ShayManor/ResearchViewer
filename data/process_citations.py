import duckdb
import requests

# 1) Get DOI for all papers from arxiv id
# 2) Get author list and update papers table
# 3) Get citations list from DOIs (of DOIs) and update papers table

conn = duckdb.connect("../data.db")
res = conn.execute("SELECT id, doi FROM papers where doi is null limit 10;").fetchdf()


def process_doi(dois: list[str]):
    for idx, (paper_id, doi) in enumerate(dois):
        if doi is None:
            dois[idx] = f"10.48550/arXiv.{paper_id}"

def get_author_ids(dois: str, *, prefer_orcid: bool = True) -> list[str]:
    """
    Returns an id for each author on each paper (doi)
    - If prefer_orcid=True and ORCID exists, returns ORCID URL for that author
    - Otherwise returns OpenAlex Author ID (https://openalex.org/A...)

    NOTE: OpenAlex truncates authorships at 100 authors in the API.
    """
    url = "https://api.openalex.org/works"

    filter_str = "|".join(
        [f"doi:https://doi.org/{d}" for d in dois]
    )  # dois = list of 50
    r = requests.get(
        url,
        params={"filter": filter_str, "per-page": 50, "select": "doi,authorships"},
        timeout=20,
    )

    r.raise_for_status()
    w = r.json()["results"]

    ids: list[str] = []
    for a in w.get("authorships", []):
        author = a.get("author", {}) or {}
        openalex_id = author.get("id")  # unique author id
        orcid = author.get("orcid")  # may be None

        if prefer_orcid and orcid:
            ids.append(orcid)
        elif openalex_id:
            ids.append(openalex_id)

    return ids


print(res.values)

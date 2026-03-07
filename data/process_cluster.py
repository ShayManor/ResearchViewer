import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import duckdb
import numpy as np
import pandas as pd
from adapters import AutoAdapterModel
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize
from tqdm import tqdm
from transformers import AutoTokenizer

_LABEL_TOKENIZER = None
_LABEL_MODEL = None
_LABEL_DEVICE = None

try:
    from transformers import AutoTokenizer
    from adapters import AutoAdapterModel

    SPECTER2_AVAILABLE = True
except ImportError:
    AutoTokenizer = None
    AutoAdapterModel = None
    SPECTER2_AVAILABLE = False

try:
    import spacy

    _SPACY = spacy.load("en_core_web_sm", disable=["ner", "textcat"])
except Exception:
    _SPACY = None

try:
    import igraph as ig

    IGRAPH_AVAILABLE = True
except ImportError:
    ig = None
    IGRAPH_AVAILABLE = False

try:
    import torch

    TORCH_AVAILABLE = True
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TORCH_AVAILABLE = False
    CUDA_AVAILABLE = False

try:
    import cuml
    from cuml.cluster import KMeans as cuKMeans
    import cupy as cp

    CUML_AVAILABLE = True
except ImportError:
    CUML_AVAILABLE = False

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_DB = "../src/data.db"
DEFAULT_BUCKET_COLUMN = "primary_topic_name"
DEFAULT_TOPK_ASSIGNMENTS = 1
DEFAULT_SECONDARY_RATIO = 0.92
DEFAULT_MIN_DOCS = 40
DEFAULT_MAX_DOCS_FOR_CLUSTER_SELECTION = 4000
DEFAULT_SEED = 42

BUCKET_COLUMN_ALLOWLIST = {
    "primary_domain_name",
    "primary_field_name",
    "primary_subfield_name",
    "primary_topic_name",
}

GENERIC_BAD_TERMS = {
    "paper", "papers", "study", "studies", "method", "methods", "approach", "approaches",
    "model", "models", "task", "tasks", "result", "results", "problem", "problems", "based",
    "using", "use", "new", "novel", "learning", "analysis", "application", "applications",
    "dataset", "datasets", "data", "performance", "algorithm", "algorithms", "systems",
    "deep", "neural", "network", "networks", "artificial", "intelligence",
}

ACRONYM_MAP = {
    "nlp": "NLP", "rl": "RL", "rag": "RAG", "llm": "LLMs",
    "gnn": "GNNs", "gan": "GANs", "qa": "QA", "ir": "IR", "asr": "ASR",
}


# ── Data classes ─────────────────────────────────────────────────────────────
@dataclass
class ClusterArtifacts:
    k: int
    labels: np.ndarray
    centers: np.ndarray
    scores: np.ndarray


# ── Text helpers ──────────────────────────────────────────────────────────────
def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_text(title: Optional[str], abstract: Optional[str]) -> str:
    title = normalize_whitespace(title or "")
    abstract = normalize_whitespace(abstract or "")
    if title and abstract:
        return f"{title}. {abstract}"
    return title or abstract


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "bucket"


# ── DB schema ─────────────────────────────────────────────────────────────────
def ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS microtopics
                 (
                     microtopic_id
                     VARCHAR
                     PRIMARY
                     KEY,
                     bucket_column
                     VARCHAR
                     NOT
                     NULL,
                     bucket_value
                     VARCHAR
                     NOT
                     NULL,
                     cluster_id
                     INTEGER
                     NOT
                     NULL,
                     label
                     VARCHAR
                     NOT
                     NULL,
                     size
                     INTEGER
                     NOT
                     NULL,
                     top_terms_json
                     VARCHAR,
                     representative_titles_json
                     VARCHAR,
                     embedding_backend
                     VARCHAR
                     NOT
                     NULL,
                     cluster_model
                     VARCHAR
                     NOT
                     NULL,
                     created_at
                     TIMESTAMP
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )
                 """)
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS paper_microtopics
                 (
                     paper_id
                     VARCHAR
                     NOT
                     NULL,
                     doi
                     VARCHAR,
                     bucket_column
                     VARCHAR
                     NOT
                     NULL,
                     bucket_value
                     VARCHAR
                     NOT
                     NULL,
                     microtopic_id
                     VARCHAR
                     NOT
                     NULL,
                     rank
                     INTEGER
                     NOT
                     NULL,
                     score
                     DOUBLE
                     NOT
                     NULL,
                     is_primary
                     BOOLEAN
                     NOT
                     NULL,
                     created_at
                     TIMESTAMP
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )
                 """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_paper_microtopics_bucket ON paper_microtopics(bucket_column, bucket_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_paper_microtopics_paper ON paper_microtopics(paper_id)")


# ── Data loading ──────────────────────────────────────────────────────────────
def get_all_bucket_values(conn: duckdb.DuckDBPyConnection, bucket_column: str, min_docs: int) -> list[str]:
    rows = conn.execute(f"""
        SELECT {bucket_column}, COUNT(*) AS cnt
        FROM papers
        WHERE deleted IS NOT TRUE
          AND {bucket_column} IS NOT NULL
          AND (title IS NOT NULL OR abstract IS NOT NULL)
        GROUP BY {bucket_column}
        HAVING cnt >= ?
        ORDER BY cnt DESC
    """, [min_docs]).fetchall()
    values = [r[0] for r in rows]
    print(f"[all] Found {len(values)} bucket values in '{bucket_column}' with >= {min_docs} docs", file=sys.stderr)
    for name, cnt in rows[:10]:
        print(f"       {cnt:>7,}  {name}", file=sys.stderr)
    if len(rows) > 10:
        print(f"       ... and {len(rows) - 10} more", file=sys.stderr)
    return values


def load_all_papers(conn: duckdb.DuckDBPyConnection, bucket_column: str) -> pd.DataFrame:
    print(f"[load] Fetching all papers grouped by {bucket_column} ...", file=sys.stderr)
    t0 = time.time()
    df = conn.execute(f"""
        SELECT id, doi, title, abstract, {bucket_column} AS bucket_value
        FROM papers
        WHERE deleted IS NOT TRUE
          AND {bucket_column} IS NOT NULL
          AND (title IS NOT NULL OR abstract IS NOT NULL)
    """).df()
    df["doc_text"] = [clean_text(t, a) for t, a in zip(df["title"], df["abstract"])]
    df = df[df["doc_text"].str.len() > 20].reset_index(drop=True)
    print(f"[load] {len(df):,} papers loaded in {time.time() - t0:.1f}s", file=sys.stderr)
    return df


def load_bucket_papers(
        conn: duckdb.DuckDBPyConnection,
        bucket_column: str,
        bucket_value: str,
        limit: Optional[int],
) -> pd.DataFrame:
    sql = f"""
        SELECT id, doi, title, abstract, {bucket_column} AS bucket_value
        FROM papers
        WHERE deleted IS NOT TRUE
          AND {bucket_column} = ?
          AND (title IS NOT NULL OR abstract IS NOT NULL)
    """
    params: list = [bucket_value]
    if limit is not None:
        sql += " ORDER BY coalesce(citation_count, 0) DESC, coalesce(update_date, DATE '1970-01-01') DESC LIMIT ?"
        params.append(limit)
    df = conn.execute(sql, params).df()
    if df.empty:
        return df
    df["doc_text"] = [clean_text(t, a) for t, a in zip(df["title"], df["abstract"])]
    df = df[df["doc_text"].str.len() > 20].reset_index(drop=True)
    return df


# ── Embedding ─────────────────────────────────────────────────────────────────
def build_tfidf_embeddings(texts: list[str], seed: int) -> tuple[np.ndarray, dict]:
    print(f"[embed] TF-IDF vectorizing {len(texts):,} texts ...", file=sys.stderr)
    t0 = time.time()
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.5,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    X = vectorizer.fit_transform(texts)
    n_components = max(8, min(128, X.shape[1] - 1, X.shape[0] - 1))
    if n_components >= 8:
        svd = TruncatedSVD(n_components=n_components, random_state=seed)
        dense = svd.fit_transform(X)
    else:
        dense = X.toarray()
    dense = normalize(dense)
    print(f"[embed] TF-IDF done: shape={dense.shape} in {time.time() - t0:.1f}s", file=sys.stderr)
    return dense, {"backend": "tfidf_svd", "vectorizer": vectorizer}


class Specter2Embedder:
    def __init__(
            self,
            base_model: str = "allenai/specter2_base",
            adapter_model: str = "allenai/specter2",
            device: str | None = None,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.model = AutoAdapterModel.from_pretrained(base_model)
        self.model.load_adapter(adapter_model, source="hf", load_as="proximity", set_active=True)
        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        out = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
                return_token_type_ids=False,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            emb = outputs.last_hidden_state[:, 0, :]  # CLS token, per official example
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            out.append(emb.cpu().numpy().astype(np.float32))
        return np.vstack(out)


def build_specter2_texts(df) -> list[str]:
    sep = " [SEP] "  # simple stand-in; tokenizer will still tokenize it fine
    texts = []
    for title, abstract in zip(df["title"], df["abstract"]):
        title = (title or "").strip()
        abstract = (abstract or "").strip()
        texts.append(f"{title}{sep}{abstract}" if abstract else title)
    return texts


def build_paper_texts_for_embeddings(df: pd.DataFrame) -> list[str]:
    texts = []
    for title, abstract in zip(df["title"], df["abstract"]):
        title = normalize_whitespace(title or "")
        abstract = normalize_whitespace(abstract or "")
        if abstract:
            texts.append(f"{title} [SEP] {abstract}")
        else:
            texts.append(title)
    return texts


def build_specter2_embeddings(
        texts: list[str],
        base_model: str,
        adapter_model: str,
) -> tuple[np.ndarray, dict]:
    if not SPECTER2_AVAILABLE:
        raise RuntimeError("transformers/adapters not installed")

    device = "cuda" if CUDA_AVAILABLE else "cpu"
    batch_size = 128 if CUDA_AVAILABLE else 16

    print(f"[embed] SPECTER2 base='{base_model}' adapter='{adapter_model}' on {device.upper()}, batch={batch_size}",
          file=sys.stderr)

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoAdapterModel.from_pretrained(base_model)
    adapter_name = model.load_adapter(
        adapter_model,
        source="hf",
        load_as="specter2_proximity",
    )

    model.active_adapters = adapter_name
    # alternatively:
    # model.set_active_adapters(adapter_name)

    print(f"[embed] active_adapters={model.active_adapters}", file=sys.stderr)
    model.to(device)
    model.eval()

    out = []
    t0 = time.time()

    with torch.no_grad():
        for start in tqdm(range(0, len(texts), batch_size), desc="SPECTER2", file=sys.stderr):
            batch = texts[start:start + batch_size]
            inputs = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
                return_token_type_ids=False,
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            outputs = model(**inputs)

            # official example uses first token embedding
            emb = outputs.last_hidden_state[:, 0, :]
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            out.append(emb.cpu().numpy().astype(np.float32))

    emb = np.vstack(out)
    elapsed = time.time() - t0
    print(
        f"[embed] {len(texts):,} texts → shape={emb.shape} in {elapsed:.1f}s ({len(texts) / max(elapsed, 1e-9):.0f} texts/s)",
        file=sys.stderr)
    global _LABEL_TOKENIZER, _LABEL_MODEL, _LABEL_DEVICE
    _LABEL_TOKENIZER = tokenizer
    _LABEL_MODEL = model
    _LABEL_DEVICE = device
    return emb, {
        "backend": f"specter2:{base_model}+{adapter_model}",
        "vectorizer": None,
        "device": device,
    }


def embed_label_texts(texts: list[str]) -> np.ndarray:
    global _LABEL_TOKENIZER, _LABEL_MODEL, _LABEL_DEVICE
    if _LABEL_TOKENIZER is None or _LABEL_MODEL is None:
        raise RuntimeError("Label embedder not initialized")

    out = []
    batch_size = 64
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            inputs = _LABEL_TOKENIZER(
                batch,
                padding=True,
                truncation=True,
                max_length=64,
                return_tensors="pt",
                return_token_type_ids=False,
            )
            inputs = {k: v.to(_LABEL_DEVICE) for k, v in inputs.items()}
            outputs = _LABEL_MODEL(**inputs)
            emb = outputs.last_hidden_state[:, 0, :]
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            out.append(emb.cpu().numpy().astype(np.float32))
    return np.vstack(out)


def build_embeddings(texts: list[str], backend: str, model_name: str, seed: int) -> tuple[np.ndarray, dict]:
    if backend == "specter2":
        # model_name can be:
        #   "allenai/specter2_base|allenai/specter2"
        # or just "allenai/specter2_base", in which case adapter defaults
        if "|" in model_name:
            base_model, adapter_model = model_name.split("|", 1)
        else:
            base_model = model_name
            adapter_model = "allenai/specter2"
        return build_specter2_embeddings(texts, base_model=base_model, adapter_model=adapter_model)

    if backend == "tfidf":
        return build_tfidf_embeddings(texts, seed)

    if backend == "auto":
        try:
            base_model = "allenai/specter2_base"
            adapter_model = "allenai/specter2"
            return build_specter2_embeddings(texts, base_model=base_model, adapter_model=adapter_model)
        except Exception as exc:
            print(f"[warn] could not load SPECTER2 ({exc}); falling back to tfidf_svd", file=sys.stderr)
            return build_tfidf_embeddings(texts, seed)

    raise ValueError(f"Unknown backend: {backend!r}")


def build_cosine_knn_graph(embeddings: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nn = NearestNeighbors(
        n_neighbors=k,
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    )
    nn.fit(embeddings)
    distances, indices = nn.kneighbors(embeddings, return_distance=True)
    return distances, indices, embeddings


def choose_k_and_cluster(
        embeddings: np.ndarray,
        seed: int,
        max_docs_for_selection: int,
        knn_k: int | None,
        leiden_resolution: float | None,
        leiden_iterations: int,
        min_cluster_size: int,
) -> ClusterArtifacts:
    if not IGRAPH_AVAILABLE:
        raise RuntimeError("python-igraph is required for Leiden clustering")

    n_docs = embeddings.shape[0]
    knn_k = knn_k or choose_knn_k(n_docs)

    print(f"[cluster] cosine k-NN + Leiden | n={n_docs:,} | kNN={knn_k}", file=sys.stderr)

    distances, indices, emb = build_cosine_knn_graph(embeddings, knn_k)

    edge_weights = {}
    for i in range(n_docs):
        for j, dist in zip(indices[i], distances[i]):
            if i == j:
                continue
            a, b = (i, int(j)) if i < j else (int(j), i)
            sim = max(0.0, 1.0 - float(dist))
            if sim <= 0:
                continue
            prev = edge_weights.get((a, b))
            if prev is None or sim > prev:
                edge_weights[(a, b)] = sim

    edges = list(edge_weights.keys())
    weights = list(edge_weights.values())
    G = ig.Graph(n=n_docs, edges=edges, directed=False)
    G.es["weight"] = weights

    if leiden_resolution is not None:
        grid = [leiden_resolution]
    else:
        grid = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    best_labels = None
    best_stats = None
    best_score = None
    best_resolution = None

    for res in grid:
        labels = leiden_partition_from_graph(G, resolution=res, n_iterations=leiden_iterations)
        stats = partition_stats(labels)
        score = score_partition(stats, n_docs=n_docs, min_cluster_size=min_cluster_size)
        print(
            f"[cluster] resolution={res:.2f} | "
            f"clusters={stats['n_clusters']} | "
            f"largest={stats['largest_frac']:.3f} | "
            f"median={stats['median_size']:.1f} | "
            f"singletons={stats['singleton_frac']:.3f} | "
            f"score={score:.2f}",
            file=sys.stderr,
        )
        if best_score is None or score > best_score:
            best_score = score
            best_labels = labels
            best_stats = stats
            best_resolution = res

    print(
        f"[cluster] picked resolution={best_resolution:.2f} | "
        f"clusters={best_stats['n_clusters']}",
        file=sys.stderr,
    )

    labels = merge_small_clusters(embeddings, best_labels, min_cluster_size=min_cluster_size)
    tmp_unique = np.unique(labels)
    tmp_centers = []
    tmp_map = {}
    for pos, cid in enumerate(tmp_unique):
        idx = np.where(labels == cid)[0]
        center = emb[idx].mean(axis=0)
        center = center / (np.linalg.norm(center) + 1e-12)
        tmp_centers.append(center)
        tmp_map[cid] = pos
    tmp_centers = np.vstack(tmp_centers).astype(np.float32)
    tmp_labels = np.array([tmp_map[c] for c in labels], dtype=np.int32)

    # merge near-duplicate clusters
    labels = merge_similar_clusters(tmp_labels, tmp_centers, min_similarity=0.90)

    unique_clusters = np.unique(labels)
    centers = []
    cluster_id_to_pos = {}

    for pos, cid in enumerate(unique_clusters):
        idx = np.where(labels == cid)[0]
        center = emb[idx].mean(axis=0)
        center = center / (np.linalg.norm(center) + 1e-12)
        centers.append(center)
        cluster_id_to_pos[int(cid)] = pos

    centers = np.vstack(centers).astype(np.float32)
    scores = emb @ centers.T
    remapped_labels = np.array([cluster_id_to_pos[int(cid)] for cid in labels], dtype=np.int32)

    print(f"[cluster] Found {len(unique_clusters)} clusters after merge", file=sys.stderr)
    return ClusterArtifacts(
        k=len(unique_clusters),
        labels=remapped_labels,
        centers=centers,
        scores=scores,
    )


def merge_small_clusters(
        embeddings: np.ndarray,
        labels: np.ndarray,
        min_cluster_size: int,
) -> np.ndarray:
    unique, counts = np.unique(labels, return_counts=True)
    sizes = dict(zip(unique.tolist(), counts.tolist()))

    large_clusters = [cid for cid, sz in sizes.items() if sz >= min_cluster_size]
    if not large_clusters:
        return labels

    # centroids of large clusters
    large_centers = {}
    for cid in large_clusters:
        idx = np.where(labels == cid)[0]
        center = embeddings[idx].mean(axis=0)
        center = center / (np.linalg.norm(center) + 1e-12)
        large_centers[cid] = center

    large_ids = np.array(sorted(large_centers.keys()))
    center_matrix = np.vstack([large_centers[cid] for cid in large_ids])

    new_labels = labels.copy()

    for cid, sz in sizes.items():
        if sz >= min_cluster_size:
            continue

        idx = np.where(labels == cid)[0]
        if len(idx) == 0:
            continue

        # average similarity of this tiny cluster to large cluster centroids
        cluster_emb = embeddings[idx]
        sims = cluster_emb @ center_matrix.T
        mean_sims = sims.mean(axis=0)
        best_large = large_ids[int(np.argmax(mean_sims))]
        new_labels[idx] = best_large

    # remap to contiguous 0..K-1
    final_ids = np.unique(new_labels)
    remap = {cid: i for i, cid in enumerate(final_ids)}
    return np.array([remap[cid] for cid in new_labels], dtype=np.int32)


def merge_similar_clusters(
    labels: np.ndarray,
    centers: np.ndarray,
    min_similarity: float = 0.965,
) -> np.ndarray:
    """
    Merge only mutually nearest clusters above a very high similarity threshold.
    This avoids chain-collapse where A~B, B~C, C~D merges everything.
    """
    sims = centers @ centers.T
    np.fill_diagonal(sims, -1.0)

    k = sims.shape[0]
    nearest = np.argmax(sims, axis=1)

    # only merge mutual nearest neighbors
    merges = []
    used = set()
    for i in range(k):
        j = int(nearest[i])
        if j == i:
            continue
        if nearest[j] == i and sims[i, j] >= min_similarity:
            a, b = sorted((i, j))
            if a not in used and b not in used:
                merges.append((a, b))
                used.add(a)
                used.add(b)

    if not merges:
        return labels

    remap = {i: i for i in range(k)}
    for a, b in merges:
        remap[b] = a

    # compact ids
    root_to_new = {}
    next_id = 0
    new_labels = np.empty_like(labels)

    for idx, cid in enumerate(labels):
        root = remap[int(cid)]
        if root not in root_to_new:
            root_to_new[root] = next_id
            next_id += 1
        new_labels[idx] = root_to_new[root]

    return new_labels


# ── Labeling ──────────────────────────────────────────────────────────────────
def aggregate_cluster_keywords(
        texts: list[str], cluster_labels: np.ndarray, top_n: int = 12
) -> dict[int, list[tuple[str, float]]]:
    # Sample down if huge — keyword extraction doesn't need all docs
    MAX_SAMPLE = 5_000
    if len(texts) > MAX_SAMPLE:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(texts), size=MAX_SAMPLE, replace=False)
        texts = [texts[i] for i in idx]
        cluster_labels = cluster_labels[idx]
        print(f"[keywords] Sampled {MAX_SAMPLE:,} docs for keyword extraction", file=sys.stderr)

    vectorizer = CountVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.8,
        max_features=20000,
        strip_accents="unicode",
    )
    X = vectorizer.fit_transform(texts)
    terms = np.array(vectorizer.get_feature_names_out())
    global_freq = np.asarray(X.sum(axis=0)).ravel() + 1.0
    result: dict[int, list[tuple[str, float]]] = {}
    for cluster_id in sorted(set(cluster_labels.tolist())):
        idx = np.where(cluster_labels == cluster_id)[0]
        if len(idx) == 0:
            result[cluster_id] = []
            continue
        cluster_counts = np.asarray(X[idx].sum(axis=0)).ravel()
        scores = cluster_counts / global_freq
        top_idx = np.argsort(scores)[::-1]
        items = []
        for j in top_idx:
            if cluster_counts[j] <= 0:
                continue
            term = terms[j]
            if is_bad_label_candidate(term):
                continue
            items.append((term, float(scores[j])))
            if len(items) >= top_n:
                break
        result[cluster_id] = items
    return result


def is_bad_label_candidate(term: str) -> bool:
    t = term.lower().strip()
    if len(t) < 2:
        return True
    return all(tok in GENERIC_BAD_TERMS for tok in t.split())


def title_case_label(term: str) -> str:
    t = term.strip()
    tl = t.lower()
    if tl in ACRONYM_MAP:
        return ACRONYM_MAP[tl]
    return " ".join(ACRONYM_MAP.get(tok.lower(), tok.capitalize()) for tok in t.split())


def normalize_candidate(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\- ]+", "", s)
    return s.strip()


def is_acronym_like(s: str) -> bool:
    s = s.strip()
    return bool(re.fullmatch(r"[A-Z0-9\-]{2,10}", s))


def bad_candidate(term: str) -> bool:
    t = normalize_candidate(term)
    if not t:
        return True

    toks = t.split()
    if len(toks) == 0 or len(toks) > 4:
        return True

    if any(ch.isdigit() for ch in t):
        return True

    if all(tok in GENERIC_BAD_TERMS for tok in toks):
        return True

    # critical fix: ban 1-word labels unless they are acronyms
    if len(toks) == 1:
        return True

    # avoid phrases starting/ending with junk
    if toks[0] in GENERIC_BAD_TERMS or toks[-1] in GENERIC_BAD_TERMS:
        return True

    return False


def extract_title_candidates(rep_titles: list[str]) -> list[str]:
    out = []
    for title in rep_titles:
        title = normalize_whitespace(title)
        if not title:
            continue

        if _SPACY is not None:
            doc = _SPACY(title)
            for chunk in doc.noun_chunks:
                cand = normalize_candidate(chunk.text)
                if not bad_candidate(cand):
                    out.append(cand)

        # fallback / supplement: raw 2-4 grams from title
        toks = re.findall(r"[A-Za-z][A-Za-z\-]+", title.lower())
        for n in (4, 3, 2):
            for i in range(len(toks) - n + 1):
                cand = " ".join(toks[i:i + n])
                if not bad_candidate(cand):
                    out.append(cand)

    return out


def acronym_pairs(rep_titles: list[str]) -> dict[str, str]:
    found = {}
    pat = re.compile(r"\b([A-Za-z][A-Za-z\- ]{5,})\s+\(([A-Z]{2,10})\)")
    for title in rep_titles:
        for long_form, short_form in pat.findall(title):
            long_form = normalize_candidate(long_form)
            if not bad_candidate(long_form):
                found[short_form] = long_form
    return found


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in items:
        x = normalize_candidate(x)
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def bad_candidate(term: str) -> bool:
    t = normalize_candidate(term)
    if not t:
        return True
    if any(ch.isdigit() for ch in t):
        return True
    toks = t.split()
    if len(toks) == 0 or len(toks) > 4:
        return True
    if all(tok in GENERIC_BAD_TERMS for tok in toks):
        return True
    if len(toks) == 1 and len(toks[0]) <= 2:
        return True
    return False


def extract_title_candidates(rep_titles: list[str]) -> list[str]:
    out = []
    for title in rep_titles:
        title = normalize_whitespace(title)
        if not title:
            continue

        if _SPACY is not None:
            doc = _SPACY(title)
            for chunk in doc.noun_chunks:
                cand = normalize_candidate(chunk.text)
                if not bad_candidate(cand):
                    out.append(cand)
        else:
            # fallback: simple n-gram phrases from title
            toks = re.findall(r"[A-Za-z][A-Za-z\-]+", title.lower())
            for n in (3, 2, 1):
                for i in range(len(toks) - n + 1):
                    cand = " ".join(toks[i:i + n])
                    if not bad_candidate(cand):
                        out.append(cand)
    return out


def acronym_from_titles(rep_titles: list[str]) -> dict[str, str]:
    # finds "retrieval augmented generation (RAG)" style pairs
    found = {}
    pat = re.compile(r"\b([A-Za-z][A-Za-z\- ]{5,})\s+\(([A-Z]{2,10})\)")
    for title in rep_titles:
        for long_form, short_form in pat.findall(title):
            long_form = normalize_candidate(long_form)
            if not bad_candidate(long_form):
                found[short_form] = long_form
    return found


def score_candidates_with_embeddings(
        candidates: list[str],
        top_terms: list[str],
        rep_titles: list[str],
        cluster_center: np.ndarray,
        embed_label_texts_fn,
) -> list[tuple[str, float]]:
    candidates = [c for c in dedupe_preserve_order(candidates) if not bad_candidate(c)]
    if not candidates:
        return []

    cand_emb = embed_label_texts_fn(candidates)  # shape=(m, d)
    sims = cand_emb @ cluster_center  # cosine if normalized

    title_text = " || ".join(rep_titles).lower()
    term_text = " || ".join(top_terms).lower()

    scored = []
    for cand, sim in zip(candidates, sims):
        toks = cand.split()

        title_hits = title_text.count(cand)
        term_hits = term_text.count(cand)

        # Prefer 2-3 token phrases
        length_bonus = 0.0
        if len(toks) == 2:
            length_bonus = 0.20
        elif len(toks) == 3:
            length_bonus = 0.28
        elif len(toks) == 4:
            length_bonus = 0.18

        # reward phrases that are both semantically central and actually visible
        score = (
                2.5 * float(sim) +
                0.35 * title_hits +
                0.20 * term_hits +
                length_bonus
        )
        scored.append((cand, score))

    scored.sort(key=lambda x: (-x[1], len(x[0]), x[0]))
    return scored


def prettify_label(term: str, acronyms: dict[str, str]) -> str:
    # return acronym if it expands to this phrase
    for short_form, long_form in acronyms.items():
        if normalize_candidate(long_form) == normalize_candidate(term):
            return short_form
    return " ".join(tok.capitalize() for tok in term.split())


def pick_short_label(
        top_terms: list[str],
        rep_titles: list[str],
        bucket_value: str,
        cluster_center: np.ndarray,
) -> str:
    acronyms = acronym_pairs(rep_titles)

    candidates = []
    candidates.extend([t for t in top_terms if not bad_candidate(t)])
    candidates.extend(extract_title_candidates(rep_titles))
    candidates.extend(acronyms.values())

    ranked = score_candidates_with_embeddings(
        candidates=candidates,
        top_terms=top_terms,
        rep_titles=rep_titles,
        cluster_center=cluster_center,
        embed_label_texts_fn=embed_label_texts,
    )

    if ranked:
        return prettify_label(ranked[0][0], acronyms)

    # fallback: acronym if present
    if acronyms:
        return sorted(acronyms.keys(), key=len)[0]

    return "Other"


def representative_titles_for_cluster(
        df: pd.DataFrame, scores: np.ndarray, cluster_id: int, n: int = 5
) -> list[str]:
    idx = np.where(df["cluster_id"].to_numpy() == cluster_id)[0]
    if len(idx) == 0:
        return []
    order = idx[np.argsort(scores[idx, cluster_id])[::-1]]
    return [
        normalize_whitespace(df.iloc[j]["title"] or "")
        for j in order[:n]
        if normalize_whitespace(df.iloc[j]["title"] or "")
    ]


def make_microtopic_id(bucket_column: str, bucket_value: str, cluster_id: int) -> str:
    raw = f"{bucket_column}|{bucket_value}|{cluster_id}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:16]
    return f"mt_{slugify(bucket_value)}_{cluster_id}_{digest}"


# ── DB writes ─────────────────────────────────────────────────────────────────
def write_results(
        conn,
        df,
        bucket_column,
        bucket_value,
        cluster_scores,
        cluster_centers,
        backend_name,
        topk_assignments,
        secondary_ratio,
        replace_bucket,
):
    print(f"[write] {bucket_value!r} — building keywords for {len(df):,} docs ...", file=sys.stderr)
    if replace_bucket:
        conn.execute("DELETE FROM paper_microtopics WHERE bucket_column = ? AND bucket_value = ?",
                     [bucket_column, bucket_value])
        conn.execute("DELETE FROM microtopics WHERE bucket_column = ? AND bucket_value = ?",
                     [bucket_column, bucket_value])

    keyword_map = aggregate_cluster_keywords(df["doc_text"].tolist(), df["cluster_id"].to_numpy(), top_n=12)

    microtopic_rows = []
    microtopic_id_by_cluster: dict[int, str] = {}

    for cluster_id, group in df.groupby("cluster_id", sort=True):
        top_terms = [term for term, _ in keyword_map.get(cluster_id, [])]
        rep_titles = representative_titles_for_cluster(df, cluster_scores, cluster_id, n=5)
        label = pick_short_label(
            top_terms=top_terms,
            rep_titles=rep_titles,
            bucket_value=bucket_value,
            cluster_center=cluster_centers[int(cluster_id)],
        )
        microtopic_id = make_microtopic_id(bucket_column, bucket_value, int(cluster_id))
        microtopic_id_by_cluster[int(cluster_id)] = microtopic_id
        microtopic_rows.append((
            microtopic_id, bucket_column, bucket_value, int(cluster_id),
            label, int(len(group)),
            json.dumps(keyword_map.get(cluster_id, []), ensure_ascii=False),
            json.dumps(rep_titles, ensure_ascii=False),
            backend_name, "MiniBatchKMeans",
        ))

    best_scores = cluster_scores.max(axis=1)  # (n_docs,)
    sorted_clusters = np.argsort(cluster_scores, axis=1)[:, ::-1]  # (n_docs, k)
    threshold = (best_scores * secondary_ratio)[:, None]  # (n_docs, 1)

    paper_ids = df["id"].to_numpy()
    dois = df["doi"].to_numpy()
    id_map = np.array([microtopic_id_by_cluster[c] for c in range(cluster_scores.shape[1])])

    # Build assignment DataFrame directly (no Python loop over all rows)
    ranks_list = []
    for rank in range(min(topk_assignments, cluster_scores.shape[1])):
        cols = sorted_clusters[:, rank]
        best_scores = cluster_scores.max(axis=1)
        sorted_clusters = np.argsort(cluster_scores, axis=1)[:, ::-1]

        ranks_list = []
        for rank in range(min(topk_assignments, cluster_scores.shape[1])):
            cols = sorted_clusters[:, rank]

            if rank == 0:
                mask = np.ones(len(df), dtype=bool)
            else:
                second_scores = cluster_scores[np.arange(len(df)), cols]
                # much stricter: only keep second label if it is genuinely competitive
                mask = (
                        (second_scores >= 0.96 * best_scores) &
                        ((best_scores - second_scores) <= 0.03)
                )

            idxs = np.where(mask)[0]
            ranks_list.append(pd.DataFrame({
                "paper_id": paper_ids[idxs],
                "doi": dois[idxs],
                "bucket_column": bucket_column,
                "bucket_value": bucket_value,
                "microtopic_id": id_map[cols[idxs]],
                "rank": rank + 1,
                "score": cluster_scores[idxs, cols[idxs]].astype(float),
                "is_primary": rank == 0,
            }))
        idxs = np.where(mask)[0]
        ranks_list.append(pd.DataFrame({
            "paper_id": paper_ids[idxs],
            "doi": dois[idxs],
            "bucket_column": bucket_column,
            "bucket_value": bucket_value,
            "microtopic_id": id_map[cols[idxs]],
            "rank": rank + 1,
            "score": cluster_scores[idxs, cols[idxs]].astype(float),
            "is_primary": rank == 0,
        }))

    microtopics_df = disambiguate_duplicate_labels(pd.DataFrame(microtopic_rows, columns=[
        "microtopic_id", "bucket_column", "bucket_value", "cluster_id", "label", "size",
        "top_terms_json", "representative_titles_json", "embedding_backend", "cluster_model",
    ])).astype({
        "microtopic_id": "string", "bucket_column": "string", "bucket_value": "string",
        "cluster_id": "int32", "label": "string", "size": "int32",
        "top_terms_json": "string", "representative_titles_json": "string",
        "embedding_backend": "string", "cluster_model": "string",
    })

    assignments_df = pd.concat(ranks_list, ignore_index=True).astype({
        "paper_id": "string", "doi": "string", "bucket_column": "string",
        "bucket_value": "string", "microtopic_id": "string",
        "rank": "int32", "score": "float64", "is_primary": "bool",
    })

    t0 = time.time()

    conn.register("microtopics_df_view", microtopics_df)
    conn.execute("""
                 INSERT INTO microtopics (microtopic_id, bucket_column, bucket_value, cluster_id, label, size,
                                          top_terms_json, representative_titles_json, embedding_backend, cluster_model)
                 SELECT *
                 FROM microtopics_df_view
                 """)
    conn.unregister("microtopics_df_view")

    conn.register("assignments_df_view", assignments_df)
    conn.execute("""
                 INSERT INTO paper_microtopics (paper_id, doi, bucket_column, bucket_value, microtopic_id, rank, score,
                                                is_primary)
                 SELECT *
                 FROM assignments_df_view
                 """)
    conn.unregister("assignments_df_view")

    print(
        f"[write] Inserted {len(microtopics_df)} microtopics + {len(assignments_df):,} assignments in {time.time() - t0:.1f}s",
        file=sys.stderr)

    return microtopics_df, assignments_df


def print_bucket_summary(microtopics_df: pd.DataFrame, keyword_map_json: bool = True) -> None:
    preview = microtopics_df.sort_values(["size", "label"], ascending=[False, True])
    for _, row in preview.iterrows():
        terms = [t for t, _ in json.loads(row["top_terms_json"])[:5]]
        print(f"    [{row['size']:>5}] {row['label']:30s} | {', '.join(terms)}")


# ── Single-bucket pipeline ────────────────────────────────────────────────────
def run_pipeline(args: argparse.Namespace) -> None:
    conn = duckdb.connect(args.db)
    try:
        ensure_tables(conn)
        print(f"\n[bucket] {args.bucket_column} = {args.bucket_value!r}", file=sys.stderr)
        df = load_bucket_papers(conn, args.bucket_column, args.bucket_value, args.limit)
        if len(df) < args.min_docs:
            raise RuntimeError(
                f"Need >= {args.min_docs} docs in {args.bucket_column}={args.bucket_value!r}; found {len(df)}"
            )
        print(f"[bucket] {len(df):,} usable documents", file=sys.stderr)

        texts = build_paper_texts_for_embeddings(df)
        embeddings, meta = build_embeddings(texts, args.embedding_backend, args.embedding_model, args.seed)
        artifacts = choose_k_and_cluster(
            embeddings,
            args.seed,
            args.max_docs_for_cluster_selection,
            knn_k=args.knn_k if args.knn_k is not None else choose_knn_k(len(df)),
            leiden_resolution=args.leiden_resolution,
            leiden_iterations=args.leiden_iterations,
            min_cluster_size=args.min_cluster_size,
        )
        df["cluster_id"] = artifacts.labels

        microtopics_df, _ = write_results(
            conn=conn,
            df=df,
            bucket_column=args.bucket_column,
            bucket_value=args.bucket_value,
            cluster_scores=artifacts.scores,
            cluster_centers=artifacts.centers,
            backend_name=meta["backend"],
            topk_assignments=args.topk_assignments,
            secondary_ratio=args.secondary_ratio,
            replace_bucket=(not args.append),
        )
        conn.commit()

        print(f"\n[result] Bucket: {args.bucket_column} = {args.bucket_value}")
        print(f"[result] Documents: {len(df):,}  |  Clusters: {artifacts.k}  |  Backend: {meta['backend']}")
        print("[result] Microtopics:")
        print_bucket_summary(microtopics_df)

        if args.write_bucket_summary_json:
            _write_summary_json(args, microtopics_df, df, artifacts, meta)
    finally:
        conn.close()

def disambiguate_duplicate_labels(microtopics_df: pd.DataFrame) -> pd.DataFrame:
    df = microtopics_df.copy()

    # Count label collisions
    counts = df["label"].value_counts()
    dup_labels = set(counts[counts > 1].index.tolist())

    if not dup_labels:
        return df

    new_labels = []
    for _, row in df.iterrows():
        label = row["label"]
        if label not in dup_labels:
            new_labels.append(label)
            continue

        top_terms = [t for t, _ in json.loads(row["top_terms_json"])]
        rep_titles = json.loads(row["representative_titles_json"])

        qualifier = None

        # pick the first decent phrase that is not just the label itself
        for cand in top_terms:
            c = normalize_candidate(cand)
            if not c:
                continue
            if c == normalize_candidate(label):
                continue
            if normalize_candidate(label) in c:
                continue
            if bad_candidate(c):
                continue
            acronyms = acronym_pairs(rep_titles)
            qualifier = prettify_label(c, acronyms)
            break

        # fallback: representative-title noun phrase
        if qualifier is None:
            title_cands = extract_title_candidates(rep_titles)
            for cand in title_cands:
                c = normalize_candidate(cand)
                if not c:
                    continue
                if c == normalize_candidate(label):
                    continue
                if normalize_candidate(label) in c:
                    continue
                if bad_candidate(c):
                    continue
                qualifier = prettify_label(c)
                break

        if qualifier:
            new_labels.append(f"{label} ({qualifier})")
        else:
            new_labels.append(label)

    df["label"] = new_labels
    return df

# ── All-buckets pipeline ──────────────────────────────────────────────────────
def run_all_buckets_pipeline(args: argparse.Namespace) -> None:
    t_total = time.time()
    conn = duckdb.connect(args.db)
    ensure_tables(conn)

    bucket_values = get_all_bucket_values(conn, args.bucket_column, args.min_docs)
    if not bucket_values:
        raise RuntimeError("No eligible bucket values found.")

    # ── Step 1: Load & embed ALL papers at once ──────────────────────────────
    print(f"\n[pipeline] Step 1/3 — Load + embed all papers", file=sys.stderr)
    all_df = load_all_papers(conn, args.bucket_column)
    texts = build_paper_texts_for_embeddings(all_df)
    embeddings, meta = build_embeddings(texts, args.embedding_backend, args.embedding_model, args.seed)

    # Build bucket → slice index once
    bucket_to_idx: dict[str, np.ndarray] = {}
    for bv, grp in all_df.groupby("bucket_value"):
        bucket_to_idx[bv] = grp.index.to_numpy()

    # ── Step 2: Cluster each bucket in parallel (CPU threads) ────────────────
    print(f"\n[pipeline] Step 2/3 — Clustering {len(bucket_values)} buckets (parallel)", file=sys.stderr)

    def cluster_bucket(bv: str) -> tuple[str, Optional[tuple], str]:
        idx = bucket_to_idx.get(bv)
        if idx is None or len(idx) < args.min_docs:
            return bv, None, f"skipped ({len(idx) if idx is not None else 0} docs)"
        df_b = all_df.iloc[idx].reset_index(drop=True)
        emb_b = embeddings[idx]
        t0 = time.time()
        artifacts = choose_k_and_cluster(
            emb_b,
            args.seed,
            args.max_docs_for_cluster_selection,
            knn_k=args.knn_k,
            leiden_resolution=args.leiden_resolution,
            leiden_iterations=args.leiden_iterations,
        )
        df_b["cluster_id"] = artifacts.labels
        return bv, (df_b, artifacts), f"k={artifacts.k}, n={len(df_b):,} in {time.time() - t0:.1f}s"

    # Use threads (GIL released in numpy/cuml; silhouette_score is the bottleneck)
    max_workers = min(args.cluster_workers, os.cpu_count() or 4)
    print(f"[pipeline] Cluster workers: {max_workers}", file=sys.stderr)
    clustered: list[tuple[str, tuple]] = []
    skipped = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(cluster_bucket, bv): bv for bv in bucket_values}
        pbar = tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Clustering", file=sys.stderr)
        for fut in pbar:
            bv, payload, msg = fut.result()
            if payload:
                clustered.append((bv, payload))
                pbar.set_postfix_str(f"ok={len(clustered)} skip={skipped}")
            else:
                skipped += 1
                print(f"  [skip] {bv}: {msg}", file=sys.stderr)

    print(f"[pipeline] Clustered {len(clustered)}, skipped {skipped}", file=sys.stderr)

    # ── Step 3: Write to DB sequentially ─────────────────────────────────────
    print(f"\n[pipeline] Step 3/3 — Writing {len(clustered)} buckets to DB ...", file=sys.stderr)
    for bv, (df_b, artifacts) in tqdm(clustered, desc="Writing", file=sys.stderr):
        microtopics_df, _ = write_results(
            conn=conn,
            df=df_b,
            bucket_column=args.bucket_column,
            bucket_value=bv,
            cluster_scores=artifacts.scores,
            cluster_centers=artifacts.centers,
            backend_name=meta["backend"],
            topk_assignments=args.topk_assignments,
            secondary_ratio=args.secondary_ratio,
            replace_bucket=(not args.append),
        )
        preview = microtopics_df.sort_values("size", ascending=False)
        labels = [f"{r['label']}({r['size']})" for _, r in preview.iterrows()]
        print(f"  [write] {bv!r:40s} → {', '.join(labels)}", file=sys.stderr)
    conn.commit()
    conn.close()

    elapsed = time.time() - t_total
    print(
        f"\n[pipeline] ✓ Done — {len(clustered)} buckets in {elapsed:.1f}s ({elapsed / max(len(clustered), 1):.1f}s/bucket avg)",
        file=sys.stderr)


# ── JSON summary helper ───────────────────────────────────────────────────────
def _write_summary_json(
        args: argparse.Namespace,
        microtopics_df: pd.DataFrame,
        df: pd.DataFrame,
        artifacts: ClusterArtifacts,
        meta: dict,
) -> None:
    preview = microtopics_df.sort_values(["size", "label"], ascending=[False, True])
    out = {
        "bucket_column": args.bucket_column,
        "bucket_value": args.bucket_value,
        "n_documents": int(len(df)),
        "n_clusters": int(artifacts.k),
        "embedding_backend": meta["backend"],
        "microtopics": [
            {
                "microtopic_id": r["microtopic_id"],
                "label": r["label"],
                "size": int(r["size"]),
                "top_terms": json.loads(r["top_terms_json"]),
                "representative_titles": json.loads(r["representative_titles_json"]),
            }
            for _, r in preview.iterrows()
        ],
    }
    with open(args.write_bucket_summary_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[result] Wrote summary JSON: {args.write_bucket_summary_json}")


def choose_knn_k(n_docs: int) -> int:
    # conservative, bucket-size-aware defaults
    if n_docs < 500:
        return 15
    if n_docs < 2_000:
        return 20
    if n_docs < 10_000:
        return 30
    if n_docs < 50_000:
        return 40
    return 50


def leiden_partition_from_graph(
        G,
        resolution: float,
        n_iterations: int,
) -> np.ndarray:
    part = G.community_leiden(
        objective_function="modularity",
        weights="weight",
        resolution=resolution,
        n_iterations=n_iterations,
    )
    return np.array(part.membership, dtype=np.int32)


def partition_stats(labels: np.ndarray) -> dict:
    unique, counts = np.unique(labels, return_counts=True)
    counts = np.sort(counts)[::-1]
    n = len(labels)
    return {
        "n_clusters": int(len(unique)),
        "largest_frac": float(counts[0] / n),
        "singleton_frac": float((counts == 1).sum() / max(len(counts), 1)),
        "small_frac": float((counts < 10).sum() / max(len(counts), 1)),
        "median_size": float(np.median(counts)),
    }


def score_partition(stats: dict, n_docs: int, min_cluster_size: int) -> float:
    # target cluster count grows slowly with dataset size
    target_min = max(4, int(np.sqrt(n_docs) / 6))
    target_max = max(8, int(np.sqrt(n_docs) / 2.5))

    score = 0.0

    k = stats["n_clusters"]
    if k == 1:
        return -1e9

    # prefer a moderate number of clusters
    if k < target_min:
        score -= 5.0 * (target_min - k)
    elif k > target_max:
        score -= 1.5 * (k - target_max)

    # penalize one giant dominant cluster
    score -= 25.0 * max(0.0, stats["largest_frac"] - 0.35)

    # penalize fragmentation
    score -= 10.0 * stats["singleton_frac"]
    score -= 8.0 * stats["small_frac"]

    # reward reasonable median cluster size
    score -= abs(stats["median_size"] - min_cluster_size * 1.8) / max(min_cluster_size, 1)

    return score


# ── CLI ───────────────────────────────────────────────────────────────────────
def validate_bucket_column(column: str) -> None:
    if column not in BUCKET_COLUMN_ALLOWLIST:
        allowed = ", ".join(sorted(BUCKET_COLUMN_ALLOWLIST))
        raise ValueError(f"--bucket-column must be one of: {allowed}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Cluster papers inside OpenAlex buckets into short-labeled microtopics. "
                    "Pass --bucket-value all to process every bucket in one shot."
    )
    p.add_argument("--db", default=DEFAULT_DB, help="Path to DuckDB database")
    p.add_argument("--bucket-column", default=DEFAULT_BUCKET_COLUMN,
                   help=f"OpenAlex bucket column. One of: {', '.join(sorted(BUCKET_COLUMN_ALLOWLIST))}")
    p.add_argument("--bucket-value", default="Natural Language Processing Techniques",
                   help="Exact bucket value, or 'all' to process every bucket")
    p.add_argument("--limit", type=int, default=None, help="Cap docs per bucket (debug)")
    p.add_argument("--min-docs", type=int, default=DEFAULT_MIN_DOCS,
                   help="Minimum docs required to cluster a bucket")
    p.add_argument("--embedding-backend", choices=["auto", "tfidf", "specter2"], default="auto")
    p.add_argument("--embedding-model", default="allenai/specter2_base|allenai/specter2",
                   help="For specter2: 'base|adapter'. Example: allenai/specter2_base|allenai/specter2")
    p.add_argument("--knn-k", type=int, default=None,
                   help="Number of cosine nearest neighbors for graph clustering")
    p.add_argument("--min-cluster-size", type=int, default=25,
                   help="Merge clusters smaller than this into nearest larger cluster")
    p.add_argument("--leiden-resolution", type=float, default=None,
                   help="Higher = more, smaller clusters")
    p.add_argument("--leiden-iterations", type=int, default=4,
                   help="Leiden refinement iterations")
    p.add_argument("--topk-assignments", type=int, default=1,
                   help="Max microtopic labels per paper")
    p.add_argument("--secondary-ratio", type=float, default=DEFAULT_SECONDARY_RATIO,
                   help="Keep secondary label if sim >= best * ratio")
    p.add_argument("--append", action="store_true", help="Append instead of replacing bucket results")
    p.add_argument("--max-docs-for-cluster-selection", type=int, default=DEFAULT_MAX_DOCS_FOR_CLUSTER_SELECTION,
                   help="Max microtopic labels per paper")
    p.add_argument("--cluster-workers", type=int, default=4,
                   help="Parallel threads for clustering in --bucket-value all mode")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--k", type=int, default=None,
                   help="Force number of clusters for a bucket")
    p.add_argument("--write-bucket-summary-json", default=None,
                   help="Write a JSON summary for a single-bucket run")
    return p


def main() -> None:
    args = build_parser().parse_args()
    validate_bucket_column(args.bucket_column)
    if args.bucket_value.strip().lower() == "all":
        run_all_buckets_pipeline(args)
    else:
        run_pipeline(args)


if __name__ == "__main__":
    main()

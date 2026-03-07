import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


DEFAULT_DB = "../src/data.db"
DEFAULT_BUCKET_COLUMN = "primary_subfield_name"
DEFAULT_TOPK_ASSIGNMENTS = 2
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
    "deep", "neural", "network", "networks", "artificial", "intelligence"
}

SHORT_LABEL_RULES = [
    ("reinforcement learning", "RL"),
    ("computer vision", "Computer Vision"),
    ("vision language", "Vision-Language"),
    ("natural language processing", "NLP"),
    ("language model", "Language Models"),
    ("large language model", "LLMs"),
    ("retrieval augmented generation", "RAG"),
    ("question answering", "QA"),
    ("information retrieval", "IR"),
    ("machine translation", "Machine Translation"),
    ("graph neural network", "GNNs"),
    ("graph representation learning", "Graph Learning"),
    ("graph learning", "Graph Learning"),
    ("generative adversarial network", "GANs"),
    ("object detection", "Object Detection"),
    ("image segmentation", "Segmentation"),
    ("image classification", "Image Classification"),
    ("benchmark", "Benchmarking"),
    ("evaluation", "Benchmarking"),
    ("diffusion model", "Diffusion"),
    ("multimodal", "Multimodal"),
    ("self supervised", "Self-Supervised"),
    ("contrastive learning", "Contrastive Learning"),
    ("federated learning", "Federated Learning"),
    ("speech recognition", "ASR"),
    ("automatic speech recognition", "ASR"),
    ("protein", "Protein Modeling"),
    ("molecule", "Molecular Modeling"),
    ("time series", "Time Series"),
    ("recommendation", "Recommendation Systems"),
    ("anomaly detection", "Anomaly Detection"),
    ("causal inference", "Causal Inference"),
    ("imitation learning", "Imitation Learning"),
    ("offline reinforcement learning", "Offline RL"),
    ("policy optimization", "Policy Optimization"),
]

ACRONYM_MAP = {
    "nlp": "NLP",
    "rl": "RL",
    "rag": "RAG",
    "llm": "LLMs",
    "gnn": "GNNs",
    "gan": "GANs",
    "qa": "QA",
    "ir": "IR",
    "asr": "ASR",
}


@dataclass
class ClusterArtifacts:
    k: int
    labels: np.ndarray
    centers: np.ndarray
    scores: np.ndarray


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


def ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS microtopics (
            microtopic_id VARCHAR PRIMARY KEY,
            bucket_column VARCHAR NOT NULL,
            bucket_value VARCHAR NOT NULL,
            cluster_id INTEGER NOT NULL,
            label VARCHAR NOT NULL,
            size INTEGER NOT NULL,
            top_terms_json VARCHAR,
            representative_titles_json VARCHAR,
            embedding_backend VARCHAR NOT NULL,
            cluster_model VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_microtopics (
            paper_id VARCHAR NOT NULL,
            doi VARCHAR,
            bucket_column VARCHAR NOT NULL,
            bucket_value VARCHAR NOT NULL,
            microtopic_id VARCHAR NOT NULL,
            rank INTEGER NOT NULL,
            score DOUBLE NOT NULL,
            is_primary BOOLEAN NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_paper_microtopics_bucket ON paper_microtopics(bucket_column, bucket_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_paper_microtopics_paper ON paper_microtopics(paper_id)")


def load_bucket_papers(conn: duckdb.DuckDBPyConnection, bucket_column: str, bucket_value: str, limit: Optional[int]) -> pd.DataFrame:
    sql = f"""
        SELECT
            id,
            doi,
            title,
            abstract,
            {bucket_column} AS bucket_value
        FROM papers
        WHERE deleted IS NOT TRUE
          AND {bucket_column} = ?
          AND (title IS NOT NULL OR abstract IS NOT NULL)
    """
    params = [bucket_value]
    if limit is not None:
        sql += " ORDER BY coalesce(citation_count, 0) DESC, coalesce(update_date, DATE '1970-01-01') DESC LIMIT ?"
        params.append(limit)
    df = conn.execute(sql, params).df()
    if df.empty:
        return df
    df["doc_text"] = [clean_text(t, a) for t, a in zip(df["title"], df["abstract"])]
    df = df[df["doc_text"].str.len() > 20].reset_index(drop=True)
    return df


def build_tfidf_embeddings(texts: list[str], seed: int) -> tuple[np.ndarray, dict]:
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
    meta = {"backend": "tfidf_svd", "vectorizer": vectorizer}
    return dense, meta


def build_sentence_transformer_embeddings(texts: list[str], model_name: str) -> tuple[np.ndarray, dict]:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed")
    model = SentenceTransformer(model_name)
    emb = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    emb = np.asarray(emb, dtype=np.float32)
    return emb, {"backend": f"sentence_transformer:{model_name}", "vectorizer": None}


def build_embeddings(texts: list[str], backend: str, model_name: str, seed: int) -> tuple[np.ndarray, dict]:
    if backend == "sentence-transformer":
        try:
            return build_sentence_transformer_embeddings(texts, model_name)
        except Exception as exc:
            print(f"[warn] sentence-transformer backend unavailable ({exc}); falling back to tfidf_svd", file=sys.stderr)
            return build_tfidf_embeddings(texts, seed)
    if backend == "tfidf":
        return build_tfidf_embeddings(texts, seed)
    if backend == "auto":
        if SentenceTransformer is not None:
            try:
                return build_sentence_transformer_embeddings(texts, model_name)
            except Exception as exc:
                print(f"[warn] could not load {model_name} ({exc}); falling back to tfidf_svd", file=sys.stderr)
        return build_tfidf_embeddings(texts, seed)
    raise ValueError(f"Unknown backend: {backend}")


def candidate_k_values(n_docs: int) -> list[int]:
    max_k = min(30, max(4, int(round(math.sqrt(n_docs / 2.0)))))
    vals = sorted(set([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30]))
    vals = [k for k in vals if 2 <= k <= max_k and k < n_docs]
    if not vals:
        vals = [2]
    return vals


def choose_k_and_cluster(embeddings: np.ndarray, seed: int, max_docs_for_selection: int) -> ClusterArtifacts:
    n_docs = embeddings.shape[0]
    if n_docs < 8:
        k = max(2, min(3, n_docs - 1))
        km = MiniBatchKMeans(n_clusters=k, random_state=seed, n_init=10, batch_size=min(1024, n_docs), max_iter=200)
        labels = km.fit_predict(embeddings)
        scores = cosine_similarity(embeddings, normalize(km.cluster_centers_))
        return ClusterArtifacts(k=k, labels=labels, centers=normalize(km.cluster_centers_), scores=scores)

    sample_idx = np.arange(n_docs)
    if n_docs > max_docs_for_selection:
        rng = np.random.default_rng(seed)
        sample_idx = rng.choice(n_docs, size=max_docs_for_selection, replace=False)
    sample = embeddings[sample_idx]

    best = None
    for k in candidate_k_values(n_docs):
        km = MiniBatchKMeans(n_clusters=k, random_state=seed, n_init=10, batch_size=min(2048, n_docs), max_iter=200)
        labels = km.fit_predict(sample)
        if len(np.unique(labels)) < 2:
            continue
        score = silhouette_score(sample, labels, metric="euclidean")
        if best is None or score > best[0]:
            best = (score, k)

    best_k = best[1] if best is not None else min(8, max(2, int(round(math.sqrt(n_docs / 2.0)))))
    km = MiniBatchKMeans(n_clusters=best_k, random_state=seed, n_init=20, batch_size=min(2048, n_docs), max_iter=200)
    labels = km.fit_predict(embeddings)
    centers = normalize(km.cluster_centers_)
    scores = cosine_similarity(embeddings, centers)
    return ClusterArtifacts(k=best_k, labels=labels, centers=centers, scores=scores)


def build_label_vectorizer() -> CountVectorizer:
    return CountVectorizer(
        stop_words="english",
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.9,
        strip_accents="unicode",
    )


def aggregate_cluster_keywords(texts: list[str], cluster_labels: np.ndarray, top_n: int = 12) -> dict[int, list[tuple[str, float]]]:
    vectorizer = build_label_vectorizer()
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
    toks = t.split()
    if all(tok in GENERIC_BAD_TERMS for tok in toks):
        return True
    return False


def title_case_label(term: str) -> str:
    t = term.strip()
    tl = t.lower()
    if tl in ACRONYM_MAP:
        return ACRONYM_MAP[tl]
    return " ".join(ACRONYM_MAP.get(tok.lower(), tok.capitalize()) for tok in t.split())


def pick_short_label(top_terms: list[str], rep_titles: list[str], bucket_value: str) -> str:
    haystack = " | ".join(top_terms + rep_titles + [bucket_value]).lower()
    for needle, label in SHORT_LABEL_RULES:
        if needle in haystack:
            return label

    # Prefer 2-3 gram phrases first.
    for term in top_terms:
        if is_bad_label_candidate(term):
            continue
        if 1 < len(term.split()) <= 3:
            return title_case_label(term)

    # If only unigrams remain, combine the best two non-generic terms.
    unigram_terms = []
    for term in top_terms:
        toks = term.split()
        if len(toks) != 1:
            continue
        if toks[0].lower() in GENERIC_BAD_TERMS:
            continue
        unigram_terms.append(toks[0])
        if len(unigram_terms) >= 2:
            break
    if unigram_terms:
        return " ".join(title_case_label(tok) for tok in unigram_terms[:2])

    return "Other"


def representative_titles_for_cluster(df: pd.DataFrame, scores: np.ndarray, cluster_id: int, n: int = 5) -> list[str]:
    idx = np.where(df["cluster_id"].to_numpy() == cluster_id)[0]
    if len(idx) == 0:
        return []
    order = idx[np.argsort(scores[idx, cluster_id])[::-1]]
    titles = []
    for j in order[:n]:
        title = normalize_whitespace(df.iloc[j]["title"] or "")
        if title:
            titles.append(title)
    return titles


def make_microtopic_id(bucket_column: str, bucket_value: str, cluster_id: int) -> str:
    raw = f"{bucket_column}|{bucket_value}|{cluster_id}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:16]
    return f"mt_{slugify(bucket_value)}_{cluster_id}_{digest}"


def write_results(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    bucket_column: str,
    bucket_value: str,
    cluster_scores: np.ndarray,
    backend_name: str,
    topk_assignments: int,
    secondary_ratio: float,
    replace_bucket: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if replace_bucket:
        conn.execute("DELETE FROM paper_microtopics WHERE bucket_column = ? AND bucket_value = ?", [bucket_column, bucket_value])
        conn.execute("DELETE FROM microtopics WHERE bucket_column = ? AND bucket_value = ?", [bucket_column, bucket_value])

    keyword_map = aggregate_cluster_keywords(df["doc_text"].tolist(), df["cluster_id"].to_numpy(), top_n=12)

    microtopic_rows = []
    assignment_rows = []
    label_by_cluster = {}
    microtopic_id_by_cluster = {}

    for cluster_id, group in df.groupby("cluster_id", sort=True):
        top_terms = [term for term, _ in keyword_map.get(cluster_id, [])]
        rep_titles = representative_titles_for_cluster(df, cluster_scores, cluster_id, n=5)
        label = pick_short_label(top_terms, rep_titles, bucket_value)
        microtopic_id = make_microtopic_id(bucket_column, bucket_value, int(cluster_id))
        microtopic_id_by_cluster[int(cluster_id)] = microtopic_id
        label_by_cluster[int(cluster_id)] = label
        microtopic_rows.append(
            (
                microtopic_id,
                bucket_column,
                bucket_value,
                int(cluster_id),
                label,
                int(len(group)),
                json.dumps(keyword_map.get(cluster_id, []), ensure_ascii=False),
                json.dumps(rep_titles, ensure_ascii=False),
                backend_name,
                "MiniBatchKMeans",
            )
        )

    for i, row in df.iterrows():
        sims = cluster_scores[i]
        order = np.argsort(sims)[::-1]
        best_score = float(sims[order[0]])
        keep = [int(order[0])]
        for c in order[1:topk_assignments]:
            score = float(sims[c])
            if score >= best_score * secondary_ratio:
                keep.append(int(c))
        for rank, cluster_id in enumerate(keep, start=1):
            assignment_rows.append(
                (
                    row["id"],
                    row["doi"],
                    bucket_column,
                    bucket_value,
                    microtopic_id_by_cluster[cluster_id],
                    rank,
                    float(sims[cluster_id]),
                    rank == 1,
                )
            )

    conn.executemany(
        """
        INSERT INTO microtopics (
            microtopic_id, bucket_column, bucket_value, cluster_id, label, size,
            top_terms_json, representative_titles_json, embedding_backend, cluster_model
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        microtopic_rows,
    )
    conn.executemany(
        """
        INSERT INTO paper_microtopics (
            paper_id, doi, bucket_column, bucket_value, microtopic_id, rank, score, is_primary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        assignment_rows,
    )

    microtopics_df = pd.DataFrame(microtopic_rows, columns=[
        "microtopic_id", "bucket_column", "bucket_value", "cluster_id", "label", "size",
        "top_terms_json", "representative_titles_json", "embedding_backend", "cluster_model"
    ])
    assignments_df = pd.DataFrame(assignment_rows, columns=[
        "paper_id", "doi", "bucket_column", "bucket_value", "microtopic_id", "rank", "score", "is_primary"
    ])
    return microtopics_df, assignments_df


def validate_bucket_column(column: str) -> None:
    if column not in BUCKET_COLUMN_ALLOWLIST:
        allowed = ", ".join(sorted(BUCKET_COLUMN_ALLOWLIST))
        raise ValueError(f"bucket-column must be one of: {allowed}")


def run_pipeline(args: argparse.Namespace) -> None:
    validate_bucket_column(args.bucket_column)
    conn = duckdb.connect(args.db)
    try:
        ensure_tables(conn)
        df = load_bucket_papers(conn, args.bucket_column, args.bucket_value, args.limit)
        if len(df) < args.min_docs:
            raise RuntimeError(
                f"Need at least {args.min_docs} usable papers in bucket {args.bucket_column}={args.bucket_value!r}; found {len(df)}"
            )

        texts = df["doc_text"].tolist()
        embeddings, meta = build_embeddings(texts, args.embedding_backend, args.embedding_model, args.seed)
        artifacts = choose_k_and_cluster(embeddings, args.seed, args.max_docs_for_cluster_selection)
        df["cluster_id"] = artifacts.labels

        microtopics_df, assignments_df = write_results(
            conn=conn,
            df=df,
            bucket_column=args.bucket_column,
            bucket_value=args.bucket_value,
            cluster_scores=artifacts.scores,
            backend_name=meta["backend"],
            topk_assignments=args.topk_assignments,
            secondary_ratio=args.secondary_ratio,
            replace_bucket=(not args.append),
        )
        conn.commit()

        print(f"Bucket: {args.bucket_column} = {args.bucket_value}")
        print(f"Documents clustered: {len(df)}")
        print(f"Chosen clusters: {artifacts.k}")
        print(f"Embedding backend: {meta['backend']}")
        print("\nMicrotopics:")
        preview = microtopics_df.sort_values(["size", "label"], ascending=[False, True])
        for _, row in preview.iterrows():
            terms = [t for t, _ in json.loads(row["top_terms_json"])[:5]]
            print(f"  - [{row['size']:>5}] {row['label']}: {', '.join(terms)}")

        if args.write_bucket_summary_json:
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
            print(f"\nWrote summary JSON: {args.write_bucket_summary_json}")
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cluster papers inside one OpenAlex bucket into short-labeled microtopics.")
    p.add_argument("--db", default=DEFAULT_DB, help="Path to DuckDB database")
    p.add_argument("--bucket-column", default=DEFAULT_BUCKET_COLUMN, help="OpenAlex bucket column to cluster within")
    p.add_argument("--bucket-value", default="Artificial Intelligence", help="Exact bucket value to cluster, e.g. 'Artificial Intelligence'")
    p.add_argument("--limit", type=int, default=None, help="Optional limit for debugging")
    p.add_argument("--min-docs", type=int, default=DEFAULT_MIN_DOCS, help="Minimum usable documents required to run")
    p.add_argument("--embedding-backend", choices=["auto", "tfidf", "sentence-transformer"], default="auto")
    p.add_argument("--embedding-model", default="all-MiniLM-L6-v2", help="SentenceTransformer model name when using sentence-transformer backend")
    p.add_argument("--topk-assignments", type=int, default=DEFAULT_TOPK_ASSIGNMENTS, help="Maximum number of labels to assign per paper")
    p.add_argument("--secondary-ratio", type=float, default=DEFAULT_SECONDARY_RATIO, help="Keep secondary labels if similarity >= best * ratio")
    p.add_argument("--append", action="store_true", help="Append instead of replacing results for this bucket")
    p.add_argument("--max-docs-for-cluster-selection", type=int, default=DEFAULT_MAX_DOCS_FOR_CLUSTER_SELECTION)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--write-bucket-summary-json", default=None)
    return p


def main() -> None:
    args = build_parser().parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()

# ResearchViewer
Arxiv dataset analyzer for CS 348 (Databases)

![API Tests](https://github.com/ShayManor/ResearchViewer/actions/workflows/test-api.yml/badge.svg)

database:
schema_name,table_name,column_count,estimated_size
main,authors,6,1721430
main,microtopics,11,11086
main,papers,31,2927463
main,paper_microtopics,9,5198926

authors:
column_name,column_type,null,key,default,extra
author_id,VARCHAR,YES,,,
name,VARCHAR,YES,,,
paper_dois,VARCHAR[],YES,,,
h_index,INTEGER,YES,,,
works_count,INTEGER,YES,,,
cited_by_count,INTEGER,YES,,,

papers:
column_name,column_type,null,key,default,extra
id,VARCHAR,YES,,,
submitter,VARCHAR,YES,,,
authors,VARCHAR,YES,,,
title,VARCHAR,YES,,,
comments,VARCHAR,YES,,,
journal-ref,VARCHAR,YES,,,
doi,VARCHAR,YES,,,
report-no,VARCHAR,YES,,,
categories,VARCHAR,YES,,,
license,VARCHAR,YES,,,
abstract,VARCHAR,YES,,,
versions,"STRUCT(""version"" VARCHAR, created VARCHAR)[]",YES,,,
update_date,DATE,YES,,,
authors_parsed,VARCHAR[][],YES,,,
author_ids,VARCHAR[],YES,,,
deleted,BOOLEAN,YES,,,
citations,VARCHAR[],YES,,,
citation_count,INTEGER,YES,,,
oa_work_id,VARCHAR,YES,,,
primary_topic_id,VARCHAR,YES,,,
primary_topic_name,VARCHAR,YES,,,
primary_topic_score,DOUBLE,YES,,,
primary_subfield_id,VARCHAR,YES,,,
primary_subfield_name,VARCHAR,YES,,,
primary_field_id,VARCHAR,YES,,,
primary_field_name,VARCHAR,YES,,,
primary_domain_id,VARCHAR,YES,,,
primary_domain_name,VARCHAR,YES,,,
topics_json,VARCHAR,YES,,,
topics_fetched,BOOLEAN,YES,,,
topics_updated_at,TIMESTAMP,YES,,,

microtopics:
column_name,column_type,null,key,default,extra
microtopic_id,VARCHAR,NO,PRI,,
bucket_column,VARCHAR,NO,,,
bucket_value,VARCHAR,NO,,,
cluster_id,INTEGER,NO,,,
label,VARCHAR,NO,,,
size,INTEGER,NO,,,
top_terms_json,VARCHAR,YES,,,
representative_titles_json,VARCHAR,YES,,,
embedding_backend,VARCHAR,NO,,,
cluster_model,VARCHAR,NO,,,
created_at,TIMESTAMP,YES,,CURRENT_TIMESTAMP,

paper_microtopics:
column_name,column_type,null,key,default,extra
paper_id,VARCHAR,NO,,,
doi,VARCHAR,YES,,,
bucket_column,VARCHAR,NO,,,
bucket_value,VARCHAR,NO,,,
microtopic_id,VARCHAR,NO,,,
rank,INTEGER,NO,,,
score,DOUBLE,NO,,,
is_primary,BOOLEAN,NO,,,
created_at,TIMESTAMP,YES,,CURRENT_TIMESTAMP,


TODO:
1) Fix the many many bugs in the frontend
2) Put API + Database onto GCE/Runpod that serves frontend 
3) HTTPS + Networking + Redis
## Features

### Paper Analyzer
1) For each paper (2.1 million records), get data on authors, citation number, keywords, journal, subject, and time
2) Allow sorting / analyzing to get metrics based on these units
3) Make charts showing change over certain metrics
4) See whole graph where edges are citations or author and colored by subject.

### Recommender

1) Input recent papers you've read and get suggestions for similar papers (from the graph) by keeping small copy of read papers + likely neighbors

### Schema

1) Paper Table: Title, Abstract, Doi, Citations List (of DOIs), authors (IDs), keywords, journal, subject, submission time
2) Author Table: Author ID, Author name, Author Paper DOIs, H-Index?
3) Users: Username, Password, Read Papers, Subjects of interest, Candidate Next Papers

## ResearchViewer API Specification

> Defines every REST endpoint, request/response shape, and database schema needed to power the frontend.
> Base URL: `http://localhost:8080`

---

## New Tables

These tables are needed in addition to the existing `papers`, `authors`, `microtopics`, and `paper_microtopics`.

### `users`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `INTEGER` | NO | auto-increment PK | |
| `username` | `VARCHAR` | NO | | unique |
| `email` | `VARCHAR` | NO | | unique |
| `password_hash` | `VARCHAR` | NO | | salt$hash format |
| `linked_author_id` | `VARCHAR` | YES | `NULL` | FK → authors.author_id |
| `focus_topics` | `VARCHAR[]` | YES | `[]` | arXiv category codes |
| `created_at` | `TIMESTAMP` | NO | `CURRENT_TIMESTAMP` | |

### `user_reading_list`

Tracks which papers a user has saved to read. Ordered, deduplicated.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `user_id` | `INTEGER` | NO | | FK → users.id |
| `paper_id` | `VARCHAR` | NO | | FK → papers.id (arXiv ID) |
| `added_at` | `TIMESTAMP` | NO | `CURRENT_TIMESTAMP` | |

Unique constraint on `(user_id, paper_id)`.

### `user_read_history`

Tracks papers a user has marked as read, with date. A paper can be in reading_list but not yet read, or read but removed from the list.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `user_id` | `INTEGER` | NO | | FK → users.id |
| `paper_id` | `VARCHAR` | NO | | FK → papers.id |
| `read_at` | `DATE` | NO | `CURRENT_DATE` | |

Unique constraint on `(user_id, paper_id)`.

### `user_publications`

User-entered publications (their own work). Separate from the papers table since these may not exist in arXiv.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `INTEGER` | NO | auto-increment PK | |
| `user_id` | `INTEGER` | NO | | FK → users.id |
| `title` | `VARCHAR` | NO | | |
| `venue` | `VARCHAR` | YES | | conference, journal, or "Preprint" |
| `year` | `INTEGER` | NO | | |
| `doi` | `VARCHAR` | YES | | optional external DOI |
| `citation_count` | `INTEGER` | NO | `0` | user-entered or fetched |
| `coauthors` | `VARCHAR[]` | YES | `[]` | list of coauthor names |
| `created_at` | `TIMESTAMP` | NO | `CURRENT_TIMESTAMP` | |

---

## API Endpoints

### 1. Health

#### `GET /api/health`

Returns API status and database stats.

**Response `200`:**
```json
{
  "status": "healthy",
  "database": "connected",
  "paper_count": 2927463,
  "author_count": 1721430,
  "microtopic_count": 11086
}
```

---

### 2. Papers

#### `GET /api/papers`

Search/list papers with filters. Supports pagination.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `keyword` | string | — | Searches title, abstract, authors (ILIKE) |
| `subject` | string | — | arXiv category prefix match on `categories` |
| `author` | string | — | ILIKE match on `authors` field |
| `microtopic_id` | string | — | Papers in a specific microtopic (joins paper_microtopics) |
| `start_date` | date | — | `update_date >= ?` |
| `end_date` | date | — | `update_date <= ?` |
| `min_citations` | int | — | `citation_count >= ?` |
| `max_citations` | int | — | `citation_count <= ?` |
| `sort_by` | string | `citation_count` | One of: `citation_count`, `update_date`, `title` |
| `sort_order` | string | `DESC` | `ASC` or `DESC` |
| `page` | int | 1 | |
| `per_page` | int | 20 | Max 100 |

**Response `200`:**
```json
{
  "papers": [
    {
      "id": "1706.03762",
      "title": "Attention Is All You Need",
      "authors": "Vaswani, Shazeer, ...",
      "abstract": "...",
      "categories": "cs.CL cs.LG",
      "citation_count": 95000,
      "update_date": "2017-06-12",
      "doi": "10.48550/arXiv.1706.03762",
      "journal-ref": "...",
      "primary_topic_name": "Transformers",
      "primary_field_name": "Computer Science"
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 543
}
```

> **Implementation note:** `total` is returned from a parallel COUNT query so the frontend can show "page X of Y". For keyword search, use `title ILIKE '%keyword%' OR abstract ILIKE '%keyword%' OR authors ILIKE '%keyword%'`.

#### `GET /api/count_papers`

Same filters as `GET /api/papers` but returns only the count.

**Response `200`:**
```json
{ "count": 2927463 }
```

#### `GET /api/papers/:id`

Get a single paper by arXiv ID (the `id` column, e.g. `1706.03762`).

**Response `200`:**
```json
{
  "id": "1706.03762",
  "title": "Attention Is All You Need",
  "authors": "Vaswani, Shazeer, ...",
  "authors_parsed": [["Vaswani", "Ashish", ""], ...],
  "author_ids": ["https://openalex.org/A123", ...],
  "abstract": "...",
  "categories": "cs.CL cs.LG",
  "citation_count": 95000,
  "update_date": "2017-06-12",
  "doi": "10.48550/arXiv.1706.03762",
  "journal-ref": "...",
  "citations": ["1409.0473", "1607.06450", ...],
  "primary_topic_id": "T123",
  "primary_topic_name": "Transformers",
  "primary_subfield_name": "NLP",
  "primary_field_name": "Computer Science",
  "primary_domain_name": "Physical Sciences",
  "microtopics": [
    { "microtopic_id": "mt_001", "label": "Self-Attention Mechanisms", "score": 0.92, "is_primary": true }
  ]
}
```

> **Implementation note:** Join `paper_microtopics` and `microtopics` to populate the `microtopics` array on the paper detail response.

**Response `404`:**
```json
{ "error": "Paper not found" }
```

#### `GET /api/papers/:id/citations`

Papers that cite this paper (i.e. papers whose `citations` array contains this ID).

**Query params:** `page`, `per_page`, `sort_by`, `sort_order` (same as `/api/papers`)

**Response `200`:**
```json
{
  "citing_papers": [ ... ],
  "count": 47,
  "page": 1,
  "per_page": 20
}
```

#### `GET /api/papers/:id/references`

Papers this paper cites (look up each DOI in the paper's `citations` array).

**Query params:** `page`, `per_page`

**Response `200`:**
```json
{
  "references": [ ... ],
  "count": 12,
  "page": 1,
  "per_page": 20
}
```

#### `POST /api/papers`

Add a paper manually. Existing endpoint.

#### `PUT /api/papers/:id`

Update a paper. Existing endpoint.

#### `DELETE /api/papers/:id`

Soft-delete. Existing endpoint.

---

### 3. Authors

#### `GET /api/authors/search`

Search authors by name.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | string | **required** | ILIKE match |
| `min_h_index` | int | — | Filter by minimum h-index |
| `min_works` | int | — | Filter by minimum works_count |
| `sort_by` | string | `cited_by_count` | One of: `cited_by_count`, `h_index`, `works_count`, `name` |
| `sort_order` | string | `DESC` | |
| `limit` | int | 10 | Max 50 |

**Response `200`:**
```json
{
  "authors": [
    {
      "author_id": "https://openalex.org/A123",
      "name": "Ashish Vaswani",
      "h_index": 42,
      "works_count": 87,
      "cited_by_count": 195000
    }
  ],
  "count": 3
}
```

#### `GET /api/authors/:author_id`

Get single author with full details.

**Response `200`:**
```json
{
  "author_id": "https://openalex.org/A123",
  "name": "Ashish Vaswani",
  "h_index": 42,
  "works_count": 87,
  "cited_by_count": 195000,
  "paper_dois": ["1706.03762", ...],
  "top_papers": [
    { "id": "1706.03762", "title": "Attention Is All You Need", "citation_count": 95000, "update_date": "2017-06-12" }
  ],
  "papers_by_year": [
    { "year": "2017", "count": 5 },
    { "year": "2018", "count": 3 }
  ],
  "citations_by_year": [
    { "year": "2017", "citations": 45000 },
    { "year": "2018", "citations": 32000 }
  ],
  "primary_topics": [
    { "topic_name": "Transformers", "paper_count": 12 }
  ]
}
```

> **Implementation note:** `top_papers` is built by joining `authors.paper_dois` → `papers` and sorting by citation_count. `papers_by_year` and `citations_by_year` aggregate from the same join. `primary_topics` aggregates `papers.primary_topic_name`.

#### `GET /api/analytics/authors/top`

Top authors by a metric.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `sort_by` | string | `h_index` | One of: `h_index`, `works_count`, `cited_by_count` |
| `subject` | string | — | Only authors with papers in this category |
| `limit` | int | 50 | Max 200 |

**Response `200`:**
```json
{
  "top_authors": [ ... ],
  "sorted_by": "h_index"
}
```

---

### 4. Microtopics

#### `GET /api/microtopics`

List microtopics with filtering.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `bucket_value` | string | — | Filter by arXiv category (e.g. `cs.LG`) |
| `min_size` | int | — | Minimum paper count in topic |
| `search` | string | — | ILIKE on `label` |
| `sort_by` | string | `size` | One of: `size`, `label`, `created_at` |
| `sort_order` | string | `DESC` | |
| `limit` | int | 50 | Max 200 |

**Response `200`:**
```json
{
  "microtopics": [
    {
      "microtopic_id": "mt_001",
      "label": "Self-Attention Mechanisms",
      "bucket_value": "cs.LG",
      "size": 342,
      "top_terms": ["attention", "transformer", "self-attention", "multi-head"],
      "representative_titles": ["Attention Is All You Need", ...]
    }
  ],
  "count": 48
}
```

> **Implementation note:** Parse `top_terms_json` and `representative_titles_json` from strings.

#### `GET /api/microtopics/:microtopic_id`

Full detail for a single microtopic including aggregated statistics.

**Response `200`:**
```json
{
  "microtopic_id": "mt_001",
  "label": "Self-Attention Mechanisms",
  "bucket_value": "cs.LG",
  "size": 342,
  "top_terms": ["attention", "transformer", ...],
  "representative_titles": [...],
  "stats": {
    "total_citations": 850000,
    "avg_citations": 2485,
    "median_citations": 120,
    "max_citations": 95000,
    "paper_count": 342,
    "year_range": "2013-2024",
    "recent_growth_pct": 45.2
  },
  "papers_by_year": [
    { "year": "2017", "count": 12, "total_citations": 142000 },
    { "year": "2018", "count": 28, "total_citations": 89000 }
  ],
  "citation_distribution": [
    { "bucket": "100k+", "count": 1 },
    { "bucket": "10k-100k", "count": 5 },
    { "bucket": "1k-10k", "count": 18 },
    { "bucket": "100-1k", "count": 67 },
    { "bucket": "10-100", "count": 124 },
    { "bucket": "0-10", "count": 127 }
  ],
  "top_authors": [
    { "name": "Vaswani, Ashish", "paper_count": 4, "total_citations": 102000 }
  ],
  "top_papers": [
    { "id": "1706.03762", "title": "Attention Is All You Need", "citation_count": 95000, "update_date": "2017-06-12", "authors": "Vaswani et al." }
  ]
}
```

> **Implementation note:**
> - Join `paper_microtopics` → `papers` on `paper_id = id`.
> - `papers_by_year`: GROUP BY `EXTRACT(YEAR FROM update_date)`, aggregate COUNT and SUM(citation_count).
> - `citation_distribution`: CASE on citation_count into buckets.
> - `top_authors`: Unnest `authors_parsed` or split `authors`, GROUP BY, ORDER BY COUNT.
> - `recent_growth_pct`: `(papers in last 2 years / total papers) * 100`.
> - `median_citations`: Use `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY citation_count)`.

#### `GET /api/microtopics/:microtopic_id/papers`

Papers belonging to a microtopic, paginated.

**Query params:** `sort_by` (`citation_count`, `update_date`, `score`), `sort_order`, `page`, `per_page`

When `sort_by=score`, sort by `paper_microtopics.score DESC`.

**Response `200`:**
```json
{
  "papers": [
    {
      "id": "1706.03762",
      "title": "...",
      "citation_count": 95000,
      "update_date": "2017-06-12",
      "authors": "...",
      "score": 0.92,
      "is_primary": true
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 342
}
```

#### `GET /api/microtopics/compare`

Compare two microtopics side by side.

**Query params:**

| Param | Type | Notes |
|-------|------|-------|
| `topic_a` | string | **required** — microtopic_id |
| `topic_b` | string | **required** — microtopic_id |

**Response `200`:**
```json
{
  "topic_a": {
    "microtopic_id": "mt_001",
    "label": "Self-Attention Mechanisms",
    "size": 342,
    "stats": { ... },
    "papers_by_year": [ ... ],
    "top_papers": [ ... ]
  },
  "topic_b": {
    "microtopic_id": "mt_045",
    "label": "Graph Neural Networks",
    "size": 218,
    "stats": { ... },
    "papers_by_year": [ ... ],
    "top_papers": [ ... ]
  },
  "overlap": {
    "shared_paper_count": 14,
    "shared_author_count": 7,
    "cross_citation_count": 23,
    "jaccard_similarity": 0.025,
    "shared_papers": [
      { "id": "...", "title": "...", "citation_count": 500 }
    ]
  }
}
```

> **Implementation note:**
> - Shared papers: INTERSECT on paper_microtopics for both topic IDs.
> - Cross-citations: papers in topic A that cite (via `citations` array) papers in topic B, and vice versa.
> - Shared authors: unnest `authors_parsed`, intersect between the two sets.

---

### 5. Topic Graph

#### `GET /api/microtopics/graph`

Returns a graph of microtopics as nodes and their relationships as edges, for the force-directed graph visualization.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `bucket_value` | string | — | Filter to topics in one arXiv category |
| `min_size` | int | 5 | Exclude tiny topics |
| `min_edge_weight` | float | 0.01 | Exclude weak edges |
| `limit` | int | 100 | Max topics to return |

**Response `200`:**
```json
{
  "nodes": [
    {
      "id": "mt_001",
      "label": "Self-Attention Mechanisms",
      "bucket_value": "cs.LG",
      "size": 342,
      "avg_citations": 2485,
      "total_citations": 850000,
      "recent_growth_pct": 45.2,
      "top_paper_title": "Attention Is All You Need"
    }
  ],
  "edges": [
    {
      "source": "mt_001",
      "target": "mt_045",
      "weight": 0.34,
      "shared_papers": 14,
      "cross_citations": 23
    }
  ],
  "node_count": 48,
  "edge_count": 156
}
```

> **Implementation note:**
> Edge weight formula: `jaccard(papers_A, papers_B) * 0.3 + cross_citation_fraction * 0.7`.
> Cross-citation fraction: `cross_citations / max(size_A, size_B)` capped at 1.0.
> Only return edges above `min_edge_weight`.

---

### 6. Analytics

#### `GET /api/analytics/papers/over-time`

Paper counts over time.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `group_by` | string | `year` | `year` or `month` |
| `subject` | string | — | arXiv category filter |
| `microtopic_id` | string | — | Filter to one microtopic |

**Response `200`:**
```json
{
  "data": [
    { "period": "2020", "count": 4523, "total_citations": 892000 }
  ],
  "group_by": "year"
}
```

> **Note:** Adding `total_citations` per period allows the frontend to chart both paper count and citation volume.

#### `GET /api/analytics/citations/distribution`

**Query params:** `subject`, `microtopic_id` (both optional filters)

**Response `200`:**
```json
{
  "distribution": [
    { "citation_range": "0", "paper_count": 1200000 },
    { "citation_range": "1-5", "paper_count": 800000 },
    { "citation_range": "6-10", "paper_count": 350000 },
    { "citation_range": "11-25", "paper_count": 200000 },
    { "citation_range": "26-50", "paper_count": 120000 },
    { "citation_range": "51-100", "paper_count": 80000 },
    { "citation_range": "101-500", "paper_count": 45000 },
    { "citation_range": "501-1000", "paper_count": 8000 },
    { "citation_range": "1001-5000", "paper_count": 3500 },
    { "citation_range": "5001-10000", "paper_count": 800 },
    { "citation_range": "10000+", "paper_count": 200 }
  ]
}
```

#### `GET /api/analytics/subjects`

Paper counts by arXiv primary category.

**Query params:** `limit` (default 20)

**Response `200`:**
```json
{
  "subjects": [
    { "subject": "cs.LG", "paper_count": 312000, "avg_citations": 45 }
  ]
}
```

> **Note:** Adding `avg_citations` helps the frontend show relative impact per field.

#### `GET /api/analytics/velocity`

Paper submission velocity over recent time periods.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `period` | string | `week` | `week` or `month` |
| `subject` | string | — | filter |
| `lookback` | int | 12 | number of periods to return |

**Response `200`:**
```json
{
  "velocity": [
    { "period_start": "2025-02-24", "period_end": "2025-03-02", "count": 502 }
  ],
  "period": "week",
  "avg": 389,
  "latest": 502,
  "delta": 57,
  "delta_pct": 12.8
}
```

> **Implementation note:** Query `SELECT COUNT(*) FROM papers WHERE update_date BETWEEN ? AND ? AND (deleted = false OR deleted IS NULL)` for each period bucket.

#### `GET /api/analytics/hot-papers`

Recently published papers with high citation growth.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `subject` | string | — | filter |
| `since` | date | 2 years ago | minimum update_date |
| `sort_by` | string | `citation_count` | or `update_date` |
| `limit` | int | 10 | |

**Response `200`:**
```json
{
  "papers": [
    {
      "id": "2303.08774",
      "title": "GPT-4 Technical Report",
      "citation_count": 7500,
      "update_date": "2023-03-15",
      "categories": "cs.CL cs.AI",
      "authors": "OpenAI"
    }
  ]
}
```

---

### 7. Users

#### `POST /api/auth/register`

Create account.

**Body:**
```json
{
  "username": "shay",
  "email": "shay@purdue.edu",
  "password": "...",
  "focus_topics": ["cs.LG", "cs.CV"]
}
```

**Response `201`:**
```json
{
  "user_id": 1,
  "username": "shay",
  "session_token": "..."
}
```

#### `POST /api/auth/login`

**Body:**
```json
{ "username": "shay", "password": "..." }
```

**Response `200`:**
```json
{
  "user_id": 1,
  "username": "shay",
  "session_token": "..."
}
```

#### `GET /api/users/:user_id`

Get user profile with all statistics.

**Response `200`:**
```json
{
  "user_id": 1,
  "username": "shay",
  "email": "shay@purdue.edu",
  "focus_topics": ["cs.LG", "cs.CV", "cs.CL"],
  "linked_author_id": "https://openalex.org/A123",
  "linked_author_name": "Shay Manor",
  "created_at": "2024-09-01",
  "stats": {
    "reading_list_count": 11,
    "papers_read_count": 11,
    "total_citations_covered": 685000,
    "avg_citations_per_read": 62272,
    "reading_pace_per_week": 1.5,
    "publication_count": 3,
    "publication_citations": 0,
    "days_since_join": 187
  },
  "reading_by_topic": [
    { "topic": "cs.CL", "count": 6 },
    { "topic": "cs.LG", "count": 8 },
    { "topic": "cs.CV", "count": 3 }
  ],
  "reading_over_time": [
    { "month": "2024-09", "count": 3 },
    { "month": "2024-10", "count": 3 }
  ]
}
```

> **Implementation note:**
> - `reading_by_topic`: Join `user_read_history` → `papers`, split `categories`, GROUP BY.
> - `reading_over_time`: GROUP BY `DATE_TRUNC('month', read_at)`.
> - `linked_author_name`: JOIN to `authors` on `linked_author_id`.
> - `reading_pace_per_week`: `papers_read_count / (days_since_join / 7)`.

#### `PUT /api/users/:user_id`

Update profile fields.

**Body (partial):**
```json
{
  "email": "new@email.com",
  "focus_topics": ["cs.LG", "cs.AI"],
  "linked_author_id": "https://openalex.org/A123"
}
```

**Response `200`:**
```json
{ "status": "updated" }
```

#### `PUT /api/users/:user_id/link-author`

Link an author profile. Validates author exists.

**Body:**
```json
{ "author_id": "https://openalex.org/A123" }
```

**Response `200`:**
```json
{
  "status": "linked",
  "author_id": "https://openalex.org/A123",
  "author_name": "Ashish Vaswani",
  "h_index": 42,
  "works_count": 87
}
```

**Response `404`:** `{ "error": "Author not found" }`

#### `DELETE /api/users/:user_id/link-author`

Unlink the author.

**Response `200`:** `{ "status": "unlinked" }`

---

### 8. Reading List

#### `GET /api/users/:user_id/reading-list`

**Query params:** `sort_by` (`added_at`, `citation_count`, `update_date`), `sort_order`

**Response `200`:**
```json
{
  "papers": [
    {
      "id": "1706.03762",
      "title": "Attention Is All You Need",
      "citation_count": 95000,
      "categories": "cs.CL cs.LG",
      "update_date": "2017-06-12",
      "added_at": "2024-09-15T10:30:00Z"
    }
  ],
  "count": 11
}
```

> **Implementation note:** JOIN `user_reading_list` → `papers` on `paper_id = id`.

#### `POST /api/users/:user_id/reading-list`

Add a paper to the reading list.

**Body:**
```json
{ "paper_id": "1706.03762" }
```

**Response `201`:** `{ "status": "added", "paper_id": "1706.03762" }`

**Response `409`:** `{ "status": "already_exists" }`

#### `DELETE /api/users/:user_id/reading-list/:paper_id`

Remove paper from reading list.

**Response `200`:** `{ "status": "removed" }`

---

### 9. Read History

#### `GET /api/users/:user_id/read-history`

All papers the user has marked as read.

**Query params:** `sort_by` (`read_at`, `citation_count`), `sort_order`, `page`, `per_page`

**Response `200`:**
```json
{
  "history": [
    {
      "id": "1706.03762",
      "title": "Attention Is All You Need",
      "citation_count": 95000,
      "categories": "cs.CL cs.LG",
      "read_at": "2024-09-15"
    }
  ],
  "count": 11,
  "page": 1,
  "per_page": 50
}
```

#### `POST /api/users/:user_id/read-history`

Mark a paper as read.

**Body:**
```json
{ "paper_id": "1706.03762", "read_at": "2024-09-15" }
```

`read_at` is optional, defaults to today.

**Response `201`:** `{ "status": "added" }`

#### `DELETE /api/users/:user_id/read-history/:paper_id`

Un-mark a paper as read.

**Response `200`:** `{ "status": "removed" }`

---

### 10. Publications

#### `GET /api/users/:user_id/publications`

**Response `200`:**
```json
{
  "publications": [
    {
      "id": 1,
      "title": "Guardrail-Aware Knowledge Distillation",
      "venue": "Under Review",
      "year": 2025,
      "doi": null,
      "citation_count": 0,
      "coauthors": ["Bera, A."]
    }
  ],
  "count": 3,
  "total_citations": 0
}
```

#### `POST /api/users/:user_id/publications`

**Body:**
```json
{
  "title": "My Paper",
  "venue": "NeurIPS 2025",
  "year": 2025,
  "doi": "10.xxxx/yyyy",
  "citation_count": 0,
  "coauthors": ["Collaborator, A."]
}
```

**Response `201`:** `{ "status": "created", "id": 4 }`

#### `PUT /api/users/:user_id/publications/:pub_id`

Update a publication entry.

**Body (partial):** `{ "citation_count": 12 }`

**Response `200`:** `{ "status": "updated" }`

#### `DELETE /api/users/:user_id/publications/:pub_id`

**Response `200`:** `{ "status": "deleted" }`

---

### 11. Recommendations

#### `GET /api/users/:user_id/recommendations`

Returns papers the user hasn't read, ranked by relevance to their reading list.

**Query params:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `limit` | int | 10 | |
| `strategy` | string | `hybrid` | `citation_graph`, `topic_similarity`, or `hybrid` |

**Response `200`:**
```json
{
  "recommendations": [
    {
      "id": "2006.11239",
      "title": "Denoising Diffusion Probabilistic Models",
      "citation_count": 8200,
      "categories": "cs.LG stat.ML",
      "update_date": "2020-06-19",
      "reason": "Cited by 3 papers in your reading list",
      "score": 0.87
    }
  ],
  "count": 10
}
```

> **Implementation note (scoring):**
> 1. **Citation graph**: papers cited by or citing papers in reading list → high score.
>    - `FROM papers p JOIN user_reading_list r ON list_contains(p.citations, r.paper_id)` etc.
> 2. **Topic similarity**: papers sharing microtopics with reading list papers → medium score.
>    - Join through `paper_microtopics`.
> 3. **Hybrid**: weighted combination, boosted by citation_count.
> 4. Exclude papers already in reading list or read history.
> 5. `reason` string: generate based on which signal was strongest.

---

### 12. Reports (server-generated)

For complex reports that aggregate across many papers, have the backend do the heavy lifting.

#### `POST /api/reports/topic`

Generate a comprehensive report for one or two topics.

**Body:**
```json
{
  "microtopic_id": "mt_001",
  "compare_microtopic_id": "mt_045"
}
```

`compare_microtopic_id` is optional.

**Response `200`:**
```json
{
  "topic": {
    "microtopic_id": "mt_001",
    "label": "Self-Attention Mechanisms",
    "size": 342,
    "stats": {
      "total_citations": 850000,
      "avg_citations": 2485,
      "median_citations": 120,
      "max_citations": 95000,
      "year_range": "2013-2024",
      "recent_growth_pct": 45.2,
      "internal_citation_count": 87,
      "unique_author_count": 890
    },
    "papers_by_year": [ { "year": "2017", "count": 12, "citations": 142000 } ],
    "citation_distribution": [ { "bucket": "100k+", "count": 1 } ],
    "top_authors": [ { "name": "Vaswani", "paper_count": 4, "total_citations": 102000 } ],
    "top_papers": [ { "id": "1706.03762", "title": "...", "citation_count": 95000, "pct_of_total": 11.2 } ],
    "related_topics": [ { "microtopic_id": "mt_045", "label": "GNNs", "weight": 0.34 } ]
  },
  "comparison": {
    "topic_b": { ... },
    "overlap": {
      "shared_papers": 14,
      "shared_authors": 7,
      "cross_citations": 23,
      "jaccard": 0.025
    }
  }
}
```

> This endpoint combines all the data the frontend's report view needs in one call, avoiding multiple round trips.

#### `POST /api/reports/subject`

Report for an entire arXiv subject category.

**Body:**
```json
{
  "subject": "cs.LG",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "compare_subject": "cs.CV"
}
```

**Response `200`:**
```json
{
  "subject": {
    "category": "cs.LG",
    "paper_count": 312000,
    "stats": {
      "total_citations": 45000000,
      "avg_citations": 144,
      "median_citations": 8,
      "max_citations": 140000,
      "unique_author_count": 89000,
      "papers_per_year_avg": 62400
    },
    "papers_by_year": [ ... ],
    "citation_distribution": [ ... ],
    "top_microtopics": [
      { "microtopic_id": "mt_001", "label": "Self-Attention", "size": 342, "avg_citations": 2485 }
    ],
    "top_authors": [ ... ],
    "top_papers": [ ... ]
  },
  "comparison": { ... }
}
```

---

## Appendix: Indexing Recommendations

For the queries above to be fast on millions of rows:

```sql
-- Papers
CREATE INDEX idx_papers_categories ON papers(categories);
CREATE INDEX idx_papers_update_date ON papers(update_date);
CREATE INDEX idx_papers_citation_count ON papers(citation_count);
CREATE INDEX idx_papers_primary_topic ON papers(primary_topic_name);
CREATE INDEX idx_papers_deleted ON papers(deleted);

-- Paper microtopics
CREATE INDEX idx_pm_microtopic ON paper_microtopics(microtopic_id);
CREATE INDEX idx_pm_paper ON paper_microtopics(paper_id);
CREATE INDEX idx_pm_primary ON paper_microtopics(microtopic_id, is_primary);

-- Authors
CREATE INDEX idx_authors_name ON authors(name);
CREATE INDEX idx_authors_h_index ON authors(h_index);

-- User tables
CREATE INDEX idx_url_user ON user_reading_list(user_id);
CREATE INDEX idx_urh_user ON user_read_history(user_id);
CREATE INDEX idx_up_user ON user_publications(user_id);
```

---

## Appendix: Summary of all endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/papers` | Search/list papers (with filters) |
| `GET` | `/api/count_papers` | Count papers (with filters) |
| `GET` | `/api/papers/:id` | Single paper detail |
| `GET` | `/api/papers/:id/citations` | Papers citing this paper |
| `GET` | `/api/papers/:id/references` | Papers this paper cites |
| `POST` | `/api/papers` | Create paper |
| `PUT` | `/api/papers/:id` | Update paper |
| `DELETE` | `/api/papers/:id` | Soft-delete paper |
| `GET` | `/api/authors/search` | Search authors |
| `GET` | `/api/authors/:id` | Author detail + stats |
| `GET` | `/api/analytics/authors/top` | Top authors by metric |
| `GET` | `/api/microtopics` | List microtopics |
| `GET` | `/api/microtopics/:id` | Microtopic detail + stats |
| `GET` | `/api/microtopics/:id/papers` | Papers in a microtopic |
| `GET` | `/api/microtopics/compare` | Compare two microtopics |
| `GET` | `/api/microtopics/graph` | Topic graph (nodes + edges) |
| `GET` | `/api/analytics/papers/over-time` | Paper counts by period |
| `GET` | `/api/analytics/citations/distribution` | Citation histogram |
| `GET` | `/api/analytics/subjects` | Subject breakdown |
| `GET` | `/api/analytics/velocity` | Submission velocity |
| `GET` | `/api/analytics/hot-papers` | Trending recent papers |
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/users/:id` | User profile + stats |
| `PUT` | `/api/users/:id` | Update profile |
| `PUT` | `/api/users/:id/link-author` | Link author profile |
| `DELETE` | `/api/users/:id/link-author` | Unlink author |
| `GET` | `/api/users/:id/reading-list` | Get reading list |
| `POST` | `/api/users/:id/reading-list` | Add to reading list |
| `DELETE` | `/api/users/:id/reading-list/:paper_id` | Remove from list |
| `GET` | `/api/users/:id/read-history` | Read history |
| `POST` | `/api/users/:id/read-history` | Mark as read |
| `DELETE` | `/api/users/:id/read-history/:paper_id` | Un-read |
| `GET` | `/api/users/:id/publications` | User's publications |
| `POST` | `/api/users/:id/publications` | Add publication |
| `PUT` | `/api/users/:id/publications/:pub_id` | Update publication |
| `DELETE` | `/api/users/:id/publications/:pub_id` | Delete publication |
| `GET` | `/api/users/:id/recommendations` | Paper recommendations |
| `POST` | `/api/reports/topic` | Generate topic report |
| `POST` | `/api/reports/subject` | Generate subject report |

**Total: 37 endpoints** (12 existing to modify, 25 new)
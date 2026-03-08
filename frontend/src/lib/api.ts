const BASE = import.meta.env.VITE_API_URL || '';

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts?.headers as Record<string, string> || {}) },
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try { const b = await res.json(); if (b.error) msg = b.error; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

function qs(params: Record<string, string | number | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : '';
}

function enc(s: string) { return encodeURIComponent(s); }

export const api = {
  health: () => req<HealthRes>('/api/health'),

  // Papers
  getPapers: (p: PaperQuery = {}) => req<PapersRes>(`/api/papers${qs(p as any)}`),
  countPapers: (p: PaperQuery = {}) => req<{ count: number }>(`/api/count_papers${qs(p as any)}`),
  getPaper: (id: string) => req<PaperDetail>(`/api/papers/${enc(id)}`),
  getPaperCitations: (id: string, page = 1) =>
    req<{ citing_papers: Paper[]; count: number }>(`/api/papers/${enc(id)}/citations?page=${page}&per_page=10`),
  getPaperReferences: (id: string, page = 1) =>
    req<{ references: Paper[]; count: number }>(`/api/papers/${enc(id)}/references?page=${page}&per_page=10`),

  // Authors
  searchAuthors: (name: string, limit = 10) =>
    req<{ authors: Author[]; count: number }>(`/api/authors/search${qs({ name, limit })}`),
  getAuthor: (id: string) => req<AuthorDetail>(`/api/authors/${enc(id)}`),

  // ── 3-layer hierarchy ──────────────────────────────────────
  // Level 1: domains
  getDomains: (limit = 100) =>
    req<{ domains: DomainEntry[] }>(`/api/analytics/domains?limit=${limit}`),
  // Level 2: topics within a domain
  getTopicsInDomain: (domain: string, limit = 100) =>
    req<{ topics: TopicEntry[] }>(`/api/analytics/topics${qs({ domain, limit })}`),
  // Level 3: microtopic graph
  microtopicGraph: (p: { bucket_value?: string; min_size?: number; limit?: number } = {}) =>
    req<GraphRes>(`/api/microtopics/graph${qs(p as any)}`),

  // Microtopic detail
  getMicrotopic: (id: string) => req<MicrotopicDetail>(`/api/microtopics/${enc(id)}`),
  getMicrotopicPapers: (id: string, p: { page?: number; per_page?: number; sort_by?: string } = {}) =>
    req<{ papers: Paper[]; total: number }>(`/api/microtopics/${enc(id)}/papers${qs(p as any)}`),
  compareMicrotopics: (a: string, b: string) =>
    req<CompareRes>(`/api/microtopics/compare?topic_a=${enc(a)}&topic_b=${enc(b)}`),

  // Analytics
  subjects: (limit = 20) =>
    req<{ subjects: SubjectEntry[] }>(`/api/analytics/subjects?limit=${limit}`),
  velocity: (period = 'week', lookback = 12, subject?: string) =>
    req<VelocityRes>(`/api/analytics/velocity${qs({ period, lookback, subject })}`),
  hotPapers: (limit = 8) =>
    req<{ papers: Paper[] }>(`/api/analytics/hot-papers?limit=${limit}`),

  // Users
  getUser: (id: number) => req<UserProfile>(`/api/users/${id}`),
  linkAuthor: (uid: number, authorId: string) =>
    req<any>(`/api/users/${uid}/link-author`, { method: 'PUT', body: JSON.stringify({ author_id: authorId }) }),
  unlinkAuthor: (uid: number) =>
    req<any>(`/api/users/${uid}/link-author`, { method: 'DELETE' }),
  getReadingList: (uid: number) =>
    req<{ papers: Paper[]; count: number }>(`/api/users/${uid}/reading-list`),
  addToReadingList: (uid: number, paperId: string) =>
    req<any>(`/api/users/${uid}/reading-list`, { method: 'POST', body: JSON.stringify({ paper_id: paperId }) }),
  removeFromReadingList: (uid: number, paperId: string) =>
    req<any>(`/api/users/${uid}/reading-list/${enc(paperId)}`, { method: 'DELETE' }),
  getPublications: (uid: number) =>
    req<{ publications: Publication[]; count: number; total_citations: number }>(`/api/users/${uid}/publications`),
  addPublication: (uid: number, data: any) =>
    req<any>(`/api/users/${uid}/publications`, { method: 'POST', body: JSON.stringify(data) }),
  deletePublication: (uid: number, pubId: number) =>
    req<any>(`/api/users/${uid}/publications/${pubId}`, { method: 'DELETE' }),
  getRecommendations: (uid: number, limit = 8) =>
    req<{ recommendations: Recommendation[]; count: number }>(`/api/users/${uid}/recommendations?limit=${limit}`),
};

// ── Types ────────────────────────────────────────────────────
export interface HealthRes { status: string; paper_count: number; author_count: number; microtopic_count: number; }
export interface Paper {
  id: string; title: string; authors?: string; abstract?: string; categories?: string;
  citation_count?: number; update_date?: string; doi?: string; 'journal-ref'?: string;
  score?: number; is_primary?: boolean; added_at?: string; read_at?: string;
}
export interface PaperDetail extends Paper {
  citations?: string[]; author_ids?: string[]; primary_topic_name?: string;
  primary_field_name?: string; microtopics?: { microtopic_id: string; label: string; score: number; is_primary: boolean }[];
}
export interface PaperQuery {
  keyword?: string; subject?: string; author?: string; microtopic_id?: string;
  start_date?: string; end_date?: string; min_citations?: string; max_citations?: string;
  sort_by?: string; sort_order?: string; page?: number; per_page?: number;
}
export interface PapersRes { papers: Paper[]; page: number; per_page: number; total: number; }
export interface Author { author_id: string; name: string; h_index?: number; works_count?: number; cited_by_count?: number; }
export interface AuthorDetail extends Author {
  paper_dois?: string[]; top_papers?: Paper[]; papers_by_year?: { year: string; count: number }[];
  citations_by_year?: { year: string; citations: number }[]; primary_topics?: { topic_name: string; paper_count: number }[];
}
export interface DomainEntry { domain: string; paper_count: number; avg_citations: number; total_citations: number; }
export interface TopicEntry { topic: string; paper_count: number; avg_citations: number; total_citations: number; }
export interface SubjectEntry { subject: string; paper_count: number; avg_citations?: number; }

export interface GraphNode {
  id: string; label: string; bucket_value: string; size: number;
  avg_citations: number; total_citations: number; recent_growth_pct: number; top_paper_title?: string;
}
export interface GraphEdge { source: string; target: string; weight: number; shared_papers: number; cross_citations: number; }
export interface GraphRes { nodes: GraphNode[]; edges: GraphEdge[]; node_count: number; edge_count: number; }

export interface Microtopic {
  microtopic_id: string; label: string; bucket_value: string; size: number;
  top_terms?: string[]; representative_titles?: string[];
}
export interface MicrotopicDetail extends Microtopic {
  stats: { total_citations: number; avg_citations: number; median_citations: number; max_citations: number; paper_count: number; year_range: string; recent_growth_pct: number; internal_citation_count?: number; unique_author_count?: number };
  papers_by_year: { year: string; count: number; total_citations: number }[];
  citation_distribution: { bucket: string; count: number }[];
  top_authors: { name: string; paper_count: number; total_citations: number }[];
  top_papers: Paper[];
}
export interface CompareRes {
  topic_a: MicrotopicDetail; topic_b: MicrotopicDetail;
  overlap: { shared_paper_count: number; shared_author_count: number; cross_citation_count: number; jaccard_similarity: number };
}
export interface VelocityRes { velocity: { period_start: string; period_end: string; count: number }[]; period: string; avg: number; latest: number; delta: number; delta_pct: number; }
export interface UserProfile {
  user_id: number; username: string; email: string; focus_topics: string[];
  linked_author_id?: string; linked_author_name?: string; created_at: string;
  stats: { reading_list_count: number; papers_read_count: number; total_citations_covered: number; avg_citations_per_read: number; reading_pace_per_week: number; publication_count: number; publication_citations: number; days_since_join: number };
  reading_by_topic: { topic: string; count: number }[];
  reading_over_time: { month: string; count: number }[];
}
export interface Publication { id: number; title: string; venue?: string; year: number; doi?: string; citation_count: number; coauthors: string[]; }
export interface Recommendation extends Paper { reason: string; score: number; }

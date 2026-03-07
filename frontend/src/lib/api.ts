const BASE_URL = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers as Record<string, string> || {}) },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try { const b = await res.json(); if (b.error) msg = b.error; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  getPapers: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<{ papers: Paper[]; page: number; per_page: number }>(`/api/papers${qs}`);
  },
  countPapers: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<{ count: number }>(`/api/count_papers${qs}`);
  },
  getPaper: (doi: string) => request<Paper>(`/api/papers/${encodeURIComponent(doi)}`),
  getPaperCitations: (doi: string) => request<{ citing_papers: Paper[]; count: number }>(`/api/papers/${encodeURIComponent(doi)}/citations`),
  getPaperReferences: (doi: string) => request<{ references: Paper[]; count: number }>(`/api/papers/${encodeURIComponent(doi)}/references`),

  searchAuthors: (name: string, limit = 10) => request<{ authors: Author[]; count: number }>(`/api/authors/search?name=${encodeURIComponent(name)}&limit=${limit}`),
  getAuthor: (id: string) => request<Author>(`/api/authors/${encodeURIComponent(id)}`),
  getTopAuthors: (sortBy = 'h_index', limit = 50) => request<{ top_authors: Author[] }>(`/api/analytics/authors/top?sort_by=${sortBy}&limit=${limit}`),

  papersOverTime: (groupBy = 'year', subject?: string) => {
    let qs = `?group_by=${groupBy}`;
    if (subject) qs += `&subject=${encodeURIComponent(subject)}`;
    return request<{ data: { period: string; count: number }[] }>(`/api/analytics/papers/over-time${qs}`);
  },
  citationsDistribution: () => request<{ distribution: { citation_range: string; paper_count: number }[] }>('/api/analytics/citations/distribution'),
  subjects: (limit = 20) => request<{ subjects: { subject: string; paper_count: number }[] }>(`/api/analytics/subjects?limit=${limit}`),
  citationGraph: (limit = 80, subject?: string) => {
    let qs = `?limit=${limit}`;
    if (subject) qs += `&subject=${encodeURIComponent(subject)}`;
    return request<{ nodes: { id: string; label: string; category: string; citation_count: number }[]; edges: { source: string; target: string }[]; node_count: number; edge_count: number }>(`/api/analytics/graph${qs}`);
  },

  getUser: (userId: number) => request<UserProfile>(`/api/users/${userId}`),
  getRecommendations: (userId: number, limit = 10) => request<{ recommendations: Paper[]; count: number }>(`/api/users/${userId}/recommendations?limit=${limit}`),
  health: () => request<{ status: string }>('/api/health'),
};

export interface Paper {
  doi: string; id?: string; title: string; abstract?: string; authors?: string;
  author_ids?: string[]; categories?: string; 'journal-ref'?: string;
  citation_count?: number; citations?: string[]; update_date?: string; deleted?: boolean;
}
export interface Author {
  author_id: string; name: string; h_index?: number; works_count?: number;
  cited_by_count?: number; paper_dois?: string[];
}
export interface UserProfile {
  user_id: number; username: string; subjects_of_interest: string[]; read_papers: string[];
}

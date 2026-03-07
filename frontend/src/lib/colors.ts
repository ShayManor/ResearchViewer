const CATEGORY_COLORS: Record<string, { fill: string; border: string; text: string }> = {
  'cs.LG':  { fill: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  'cs.AI':  { fill: '#e0e7ff', border: '#6366f1', text: '#3730a3' },
  'cs.CL':  { fill: '#fce7f3', border: '#ec4899', text: '#9d174d' },
  'cs.CV':  { fill: '#fef3c7', border: '#f59e0b', text: '#92400e' },
  'cs.NE':  { fill: '#d1fae5', border: '#10b981', text: '#065f46' },
  'cs.IR':  { fill: '#e0f2fe', border: '#0ea5e9', text: '#075985' },
  'cs.RO':  { fill: '#f3e8ff', border: '#a855f7', text: '#6b21a8' },
  'stat.ML': { fill: '#ccfbf1', border: '#14b8a6', text: '#115e59' },
  'math':   { fill: '#fef9c3', border: '#eab308', text: '#713f12' },
  'physics': { fill: '#fee2e2', border: '#ef4444', text: '#991b1b' },
  'default': { fill: '#f1f5f9', border: '#94a3b8', text: '#475569' },
};

export function getCategoryColor(category: string) {
  if (!category) return CATEGORY_COLORS.default;
  const key = Object.keys(CATEGORY_COLORS).find(k => category.toLowerCase().startsWith(k.toLowerCase()));
  return CATEGORY_COLORS[key || 'default'] || CATEGORY_COLORS.default;
}

export function getCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    'cs.LG': 'Machine Learning', 'cs.AI': 'AI', 'cs.CL': 'NLP',
    'cs.CV': 'Computer Vision', 'cs.NE': 'Neural/Evolutionary',
    'cs.IR': 'Information Retrieval', 'cs.RO': 'Robotics', 'stat.ML': 'Statistical ML',
  };
  const key = Object.keys(labels).find(k => category?.startsWith(k));
  return key ? labels[key] : category?.split('.')[0] || 'Other';
}

export function getNodeRadius(paperCount: number): number {
  if (paperCount >= 10) return 42;
  if (paperCount >= 6) return 36;
  if (paperCount >= 3) return 30;
  return 24;
}

export function formatCitations(n?: number): string {
  if (n == null) return '—';
  if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k';
  return String(n);
}

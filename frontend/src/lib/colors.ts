const CAT_COLORS: Record<string, { fill: string; border: string; text: string }> = {
  'cs.LG':  { fill: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  'cs.AI':  { fill: '#e0e7ff', border: '#6366f1', text: '#3730a3' },
  'cs.CL':  { fill: '#fce7f3', border: '#ec4899', text: '#9d174d' },
  'cs.CV':  { fill: '#fef3c7', border: '#f59e0b', text: '#92400e' },
  'cs.NE':  { fill: '#d1fae5', border: '#10b981', text: '#065f46' },
  'cs.IR':  { fill: '#e0f2fe', border: '#0ea5e9', text: '#075985' },
  'cs.RO':  { fill: '#f3e8ff', border: '#a855f7', text: '#6b21a8' },
  'stat.ML': { fill: '#ccfbf1', border: '#14b8a6', text: '#115e59' },
  'cs.CR':  { fill: '#fef9c3', border: '#eab308', text: '#713f12' },
  'cs.DS':  { fill: '#fee2e2', border: '#ef4444', text: '#991b1b' },
  'cs.SE':  { fill: '#f1f5f9', border: '#64748b', text: '#334155' },
  default:  { fill: '#f1f5f9', border: '#94a3b8', text: '#475569' },
};

export function getCatColor(cat: string) {
  if (!cat) return CAT_COLORS.default;
  const k = Object.keys(CAT_COLORS).find(k => cat.startsWith(k));
  return CAT_COLORS[k || 'default'] || CAT_COLORS.default;
}

export function fmtCit(n?: number | null): string {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k';
  return String(n);
}

export function nodeRadius(paperCount: number): number {
  if (paperCount >= 500) return 48;
  if (paperCount >= 100) return 40;
  if (paperCount >= 30) return 34;
  if (paperCount >= 10) return 28;
  return 22;
}

export function subjectNodeRadius(paperCount: number): number {
  if (paperCount >= 100000) return 52;
  if (paperCount >= 50000) return 46;
  if (paperCount >= 10000) return 40;
  if (paperCount >= 1000) return 34;
  return 28;
}

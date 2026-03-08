const CAT: Record<string, { fill: string; border: string; text: string }> = {
  'Physical Sciences':  { fill: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  'Life Sciences':      { fill: '#d1fae5', border: '#10b981', text: '#065f46' },
  'Social Sciences':    { fill: '#fef3c7', border: '#f59e0b', text: '#92400e' },
  'Health Sciences':    { fill: '#fce7f3', border: '#ec4899', text: '#9d174d' },
  'cs.LG':  { fill: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  'cs.AI':  { fill: '#e0e7ff', border: '#6366f1', text: '#3730a3' },
  'cs.CL':  { fill: '#fce7f3', border: '#ec4899', text: '#9d174d' },
  'cs.CV':  { fill: '#fef3c7', border: '#f59e0b', text: '#92400e' },
  'stat.ML':{ fill: '#ccfbf1', border: '#14b8a6', text: '#115e59' },
  default:  { fill: '#f1f5f9', border: '#94a3b8', text: '#475569' },
};

// Hashes a string to a consistent index to pick a color for unknown categories
function hashColor(s: string): { fill: string; border: string; text: string } {
  const palette = [
    { fill: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
    { fill: '#e0e7ff', border: '#6366f1', text: '#3730a3' },
    { fill: '#fce7f3', border: '#ec4899', text: '#9d174d' },
    { fill: '#fef3c7', border: '#f59e0b', text: '#92400e' },
    { fill: '#d1fae5', border: '#10b981', text: '#065f46' },
    { fill: '#e0f2fe', border: '#0ea5e9', text: '#075985' },
    { fill: '#f3e8ff', border: '#a855f7', text: '#6b21a8' },
    { fill: '#ccfbf1', border: '#14b8a6', text: '#115e59' },
    { fill: '#fef9c3', border: '#eab308', text: '#713f12' },
    { fill: '#fee2e2', border: '#ef4444', text: '#991b1b' },
  ];
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return palette[Math.abs(h) % palette.length];
}

export function getCatColor(cat: string) {
  if (!cat) return CAT.default;
  if (CAT[cat]) return CAT[cat];
  // Partial match
  const k = Object.keys(CAT).find(k => cat.startsWith(k));
  if (k) return CAT[k];
  return hashColor(cat);
}

export function fmtCit(n?: number | null): string {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k';
  return String(n);
}

// Level 1: domain nodes
export function domainRadius(paperCount: number): number {
  if (paperCount >= 500000) return 60;
  if (paperCount >= 100000) return 52;
  if (paperCount >= 50000) return 44;
  if (paperCount >= 10000) return 38;
  if (paperCount >= 1000) return 32;
  return 26;
}

// Level 2: topic nodes
export function topicRadius(paperCount: number): number {
  if (paperCount >= 50000) return 48;
  if (paperCount >= 10000) return 42;
  if (paperCount >= 5000) return 36;
  if (paperCount >= 1000) return 30;
  if (paperCount >= 100) return 24;
  return 20;
}

// Level 3: microtopic nodes — BIGGER than before
export function microRadius(paperCount: number): number {
  if (paperCount >= 500) return 52;
  if (paperCount >= 200) return 46;
  if (paperCount >= 100) return 40;
  if (paperCount >= 50) return 36;
  if (paperCount >= 20) return 32;
  if (paperCount >= 10) return 28;
  return 24;
}

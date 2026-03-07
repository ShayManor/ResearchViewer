import { Database, CircleDot, Link2, TrendingUp, Wifi, WifiOff } from 'lucide-react';
import { getCategoryColor } from '../lib/colors';
import { PAPER_VELOCITY } from '../lib/dummy-data';

interface Props { totalPapers: number | null; topicCount: number; edgeCount: number; subjects: { subject: string; paper_count: number }[]; apiOnline: boolean; }

export function StatsBar({ totalPapers, topicCount, edgeCount, subjects, apiOnline }: Props) {
  const latest = PAPER_VELOCITY[PAPER_VELOCITY.length - 1];
  const prev = PAPER_VELOCITY[PAPER_VELOCITY.length - 2];
  const delta = latest.count - prev.count;
  return (
    <div className="relative z-10 flex items-center gap-4 px-5 py-2 bg-white/80 backdrop-blur-sm border-t border-gray-200/80 shrink-0 text-[10px]">
      <Stat icon={<Database size={11} />} label="Total" value={totalPapers != null ? totalPapers.toLocaleString() : '—'} />
      <Stat icon={<CircleDot size={11} />} label="Topics" value={String(topicCount)} />
      <Stat icon={<Link2 size={11} />} label="Links" value={String(edgeCount)} />
      <div className="h-3.5 w-px bg-gray-200" />
      <div className="flex items-center gap-1.5 text-gray-500">
        <TrendingUp size={11} /><span className="text-gray-400">Velocity</span>
        <span className="font-bold text-gray-700 font-mono">{latest.count}/wk</span>
        <span className={`font-mono font-medium ${delta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>({delta >= 0 ? '+' : ''}{delta})</span>
      </div>
      <div className="h-3.5 w-px bg-gray-200" />
      <div className="flex items-center gap-1.5 overflow-x-auto flex-1">
        {subjects.slice(0, 5).map(s => { const c = getCategoryColor(s.subject); return <span key={s.subject} className="shrink-0 px-1.5 py-0.5 rounded-full font-medium border" style={{ borderColor: c.border + '30', color: c.text, backgroundColor: c.fill, fontSize: '9px' }}>{s.subject} ({s.paper_count.toLocaleString()})</span>; })}
      </div>
      <div className={`flex items-center gap-1 shrink-0 px-2 py-0.5 rounded-full ${apiOnline ? 'text-emerald-600 bg-emerald-50' : 'text-gray-400 bg-gray-50'}`}>
        {apiOnline ? <Wifi size={10} /> : <WifiOff size={10} />}
        <span className="font-medium" style={{ fontSize: '9px' }}>{apiOnline ? 'API' : 'Demo'}</span>
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="flex items-center gap-1.5 text-gray-500">{icon}<span className="text-gray-400">{label}</span><span className="font-bold text-gray-700 font-mono">{value}</span></div>;
}

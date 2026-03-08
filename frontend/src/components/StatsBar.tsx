import { Database, CircleDot, Link2, TrendingUp, Wifi, WifiOff } from 'lucide-react';
import type { VelocityRes } from '../lib/api';

interface Props {
  paperCount: number | null;
  drill: { level: string; domain: string | null; topic: string | null };
  microNodeCount: number; microEdgeCount: number; topicCount: number; domainCount: number;
  velocity: VelocityRes | null; apiOnline: boolean;
}

export function StatsBar({ paperCount, drill, microNodeCount, microEdgeCount, topicCount, domainCount, velocity, apiOnline }: Props) {
  return (
    <div className="relative z-10 flex items-center gap-4 px-5 py-2 bg-white/80 backdrop-blur-sm border-t border-gray-200/80 shrink-0 text-[10px]">
      <S icon={<Database size={11} />} label="Papers" value={paperCount != null ? paperCount.toLocaleString() : '—'} />

      {drill.level === 'domain' && <S icon={<CircleDot size={11} />} label="Domains" value={String(domainCount)} />}
      {drill.level === 'topic' && <><S icon={<CircleDot size={11} />} label="Topics" value={String(topicCount)} /><span className="text-[9px] text-gray-400 truncate max-w-[120px]">{drill.domain}</span></>}
      {drill.level === 'micro' && <><S icon={<CircleDot size={11} />} label="Microtopics" value={String(microNodeCount)} /><S icon={<Link2 size={11} />} label="Edges" value={String(microEdgeCount)} /><span className="text-[9px] text-gray-400 truncate max-w-[150px]">{drill.topic}</span></>}

      <div className="h-3.5 w-px bg-gray-200" />

      {velocity && (
        <div className="flex items-center gap-1.5 text-gray-500">
          <TrendingUp size={11} /><span className="text-gray-400">Vel</span>
          <span className="font-bold text-gray-700 font-mono">{velocity.latest}/wk</span>
          <span className={`font-mono font-medium ${velocity.delta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>({velocity.delta >= 0 ? '+' : ''}{Math.round(velocity.delta)})</span>
        </div>
      )}

      <div className="flex-1" />

      <div className={`flex items-center gap-1 shrink-0 px-2 py-0.5 rounded-full ${apiOnline ? 'text-emerald-600 bg-emerald-50' : 'text-red-500 bg-red-50'}`}>
        {apiOnline ? <Wifi size={10} /> : <WifiOff size={10} />}
        <span className="font-medium" style={{ fontSize: '9px' }}>{apiOnline ? 'API' : 'Offline'}</span>
      </div>
    </div>
  );
}

function S({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="flex items-center gap-1.5 text-gray-500">{icon}<span className="text-gray-400">{label}</span><span className="font-bold text-gray-700 font-mono">{value}</span></div>;
}

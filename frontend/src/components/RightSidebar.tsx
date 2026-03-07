import { useState } from 'react';
import { BookOpen, Flame, TrendingUp, Lightbulb, X, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { formatCitations } from '../lib/colors';
import { getSeedPaper, HOT_PAPERS, PAPER_VELOCITY } from '../lib/dummy-data';
import type { Paper } from '../lib/api';

interface Props { readingList: string[]; recommendations: Paper[]; onRemoveFromList: (doi: string) => void; onAddToList: (doi: string) => void; }
type Tab = 'list' | 'hot' | 'recs';

export function RightSidebar({ readingList, recommendations, onRemoveFromList, onAddToList }: Props) {
  const [tab, setTab] = useState<Tab>('list');
  const [velocityOpen, setVelocityOpen] = useState(false);
  const readPapers = readingList.map(getSeedPaper).filter(Boolean) as Paper[];
  const maxV = Math.max(...PAPER_VELOCITY.map(v => v.count));
  const latest = PAPER_VELOCITY[PAPER_VELOCITY.length - 1];
  const prev = PAPER_VELOCITY[PAPER_VELOCITY.length - 2];
  const delta = latest.count - prev.count;

  return (
    <div className="flex flex-col h-full">
      {/* Velocity */}
      <div className="px-4 pt-4 pb-3 border-b border-gray-100 shrink-0">
        <button onClick={() => setVelocityOpen(!velocityOpen)} className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2"><TrendingUp size={13} className="text-gray-400" /><span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Velocity</span></div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-800 font-mono">{latest.count}/wk</span>
            <span className={`text-[10px] font-mono font-medium ${delta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>{delta >= 0 ? '+' : ''}{delta}</span>
            {velocityOpen ? <ChevronUp size={12} className="text-gray-400" /> : <ChevronDown size={12} className="text-gray-400" />}
          </div>
        </button>
        {velocityOpen && (
          <div className="mt-3">
            <div className="flex items-end gap-[2px] h-12">
              {PAPER_VELOCITY.map((v, i) => (
                <div key={i} className="flex-1" title={`${v.week}: ${v.count}`}>
                  <div className="w-full rounded-t" style={{ height: `${(v.count / maxV) * 100}%`, backgroundColor: i === PAPER_VELOCITY.length - 1 ? '#3b82f6' : '#cbd5e1' }} />
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-1 text-[8px] text-gray-400 font-mono">
              <span>{PAPER_VELOCITY[0].week}</span><span>{latest.week}</span>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-100 shrink-0">
        <TabBtn active={tab === 'list'} onClick={() => setTab('list')} icon={<BookOpen size={12} />} label={`List (${readingList.length})`} />
        <TabBtn active={tab === 'hot'} onClick={() => setTab('hot')} icon={<Flame size={12} />} label="Hot" />
        <TabBtn active={tab === 'recs'} onClick={() => setTab('recs')} icon={<Lightbulb size={12} />} label="For You" />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'list' && (
          <div className="p-3 space-y-1">
            {readPapers.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center"><BookOpen className="w-8 h-8 text-gray-300 mb-2" /><p className="text-sm text-gray-400">Empty reading list</p><p className="text-xs text-gray-300 mt-1">Search for papers to add</p></div>
            ) : readPapers.map(p => <PaperCard key={p.doi} paper={p} onAction={() => onRemoveFromList(p.doi)} actionIcon={<X size={11} />} />)}
          </div>
        )}
        {tab === 'hot' && (
          <div className="p-3 space-y-1">
            <p className="text-[10px] text-gray-400 mb-2 px-1">Recent high-traction papers</p>
            {HOT_PAPERS.map(p => <PaperCard key={p.doi} paper={p} onAction={() => readingList.includes(p.doi) ? onRemoveFromList(p.doi) : onAddToList(p.doi)} actionIcon={readingList.includes(p.doi) ? <X size={11} /> : <BookOpen size={11} />} highlight />)}
          </div>
        )}
        {tab === 'recs' && (
          <div className="p-3 space-y-1">
            <p className="text-[10px] text-gray-400 mb-2 px-1">Based on your reading list</p>
            {recommendations.length === 0 ? <p className="text-sm text-gray-400 text-center py-12">Add papers for recommendations</p> : recommendations.map(p => <PaperCard key={p.doi} paper={p} onAction={() => readingList.includes(p.doi) ? onRemoveFromList(p.doi) : onAddToList(p.doi)} actionIcon={readingList.includes(p.doi) ? <X size={11} /> : <BookOpen size={11} />} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick} className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-[11px] font-medium transition-colors relative ${active ? 'text-gray-800' : 'text-gray-400 hover:text-gray-500'}`}>
      {icon} {label}
      {active && <div className="absolute bottom-0 left-2 right-2 h-[2px] bg-gray-800 rounded-full" />}
    </button>
  );
}

function PaperCard({ paper, onAction, actionIcon, highlight }: { paper: Paper; onAction: () => void; actionIcon: React.ReactNode; highlight?: boolean }) {
  const arxiv = paper.doi.match(/^\d{4}\./) ? `https://arxiv.org/abs/${paper.doi}` : null;
  return (
    <div className={`group p-2.5 rounded-lg border transition-all ${highlight ? 'border-amber-200 bg-amber-50/30 hover:bg-amber-50/60' : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50/50'}`}>
      <div className="flex items-start gap-1.5">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-gray-700 leading-snug line-clamp-2">{paper.title}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className="text-[9px] text-gray-400 font-mono">{paper.doi}</span>
            {paper.citation_count != null && <span className="text-[9px] text-gray-400">{formatCitations(paper.citation_count)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          {arxiv && <a href={arxiv} target="_blank" rel="noopener noreferrer" className="p-1 rounded text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100 transition-all"><ExternalLink size={10} /></a>}
          <button onClick={onAction} className="p-1 rounded text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100 transition-all">{actionIcon}</button>
        </div>
      </div>
    </div>
  );
}

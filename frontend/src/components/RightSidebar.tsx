import { useState, useEffect } from 'react';
import { BookOpen, Flame, Lightbulb, X, ExternalLink, ChevronDown, ChevronUp, TrendingUp, Loader2, CheckCircle } from 'lucide-react';
import { fmtCit } from '../lib/colors';
import { api, type Paper, type Recommendation, type VelocityRes } from '../lib/api';

interface Props { userId: number; readingListIds: Set<string>; onRemoveFromList: (id: string) => void; onAddToList: (id: string) => void; velocity: VelocityRes | null; onMarkAsRead?: (id: string) => void; }
type Tab = 'list' | 'hot' | 'recs';

export function RightSidebar({ userId, readingListIds, onRemoveFromList, onAddToList, velocity, onMarkAsRead }: Props) {
  const [tab, setTab] = useState<Tab>('list');
  const [velOpen, setVelOpen] = useState(false);
  const [listPapers, setListPapers] = useState<Paper[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [hotPapers, setHotPapers] = useState<Paper[]>([]);
  const [hotLoading, setHotLoading] = useState(false);
  const [hotFetched, setHotFetched] = useState(false);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [recsLoading, setRecsLoading] = useState(false);

  useEffect(() => {
    if (tab !== 'list') return;
    setListLoading(true);
    api.getReadingList(userId).then(d => setListPapers(d.papers)).catch(() => setListPapers([])).finally(() => setListLoading(false));
  }, [tab, userId, readingListIds.size]);

  useEffect(() => {
    if (tab !== 'hot' || hotFetched) return;
    setHotLoading(true);
    api.hotPapers(8, userId).then(d => { setHotPapers(d.papers); setHotFetched(true); }).catch(() => {}).finally(() => setHotLoading(false));
  }, [tab, hotFetched, userId]);

  useEffect(() => {
    if (tab !== 'recs') return;
    setRecsLoading(true);
    api.getRecommendations(userId, 8).then(d => setRecs(d.recommendations)).catch(() => setRecs([])).finally(() => setRecsLoading(false));
  }, [tab, userId, readingListIds.size]);

  const vData = velocity?.velocity || [];
  const maxV = Math.max(...vData.map(v => v.count), 1);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-3 border-b border-gray-100 shrink-0">
        <button onClick={() => setVelOpen(!velOpen)} className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2"><TrendingUp size={13} className="text-gray-400" /><span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Velocity</span></div>
          <div className="flex items-center gap-2">
            {velocity ? (<><span className="text-xs font-bold text-gray-800 font-mono">{velocity.latest}/wk</span>
              <span className={`text-[10px] font-mono font-medium ${velocity.delta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>{velocity.delta >= 0 ? '+' : ''}{Math.round(velocity.delta)}</span></>)
              : <span className="text-xs text-gray-400">—</span>}
            {velOpen ? <ChevronUp size={12} className="text-gray-400" /> : <ChevronDown size={12} className="text-gray-400" />}
          </div>
        </button>
        {velOpen && vData.length > 0 && (
          <div className="mt-3">
            <div className="flex items-end gap-[2px] h-12">
              {vData.map((v, i) => (<div key={i} className="flex-1" title={`${v.period_start}: ${v.count}`}>
                <div className="w-full rounded-t" style={{ height: `${(v.count / maxV) * 100}%`, backgroundColor: i === vData.length - 1 ? '#3b82f6' : '#cbd5e1' }} /></div>))}
            </div>
            <div className="flex justify-between mt-1 text-[8px] text-gray-400 font-mono">
              <span>{vData[0]?.period_start?.slice(5)}</span><span>{vData[vData.length - 1]?.period_start?.slice(5)}</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex border-b border-gray-100 shrink-0">
        <TB active={tab === 'list'} onClick={() => setTab('list')} icon={<BookOpen size={12} />} label={`List (${readingListIds.size})`} />
        <TB active={tab === 'hot'} onClick={() => setTab('hot')} icon={<Flame size={12} />} label="Hot" />
        <TB active={tab === 'recs'} onClick={() => setTab('recs')} icon={<Lightbulb size={12} />} label="For You" />
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === 'list' && (<div className="p-3 space-y-1">
          {listLoading ? <CL /> : listPapers.length === 0 ? <Em text="Empty reading list" sub="Search for papers to add" /> :
            listPapers.map(p => <PC key={p.id} paper={p} onAction={() => onRemoveFromList(p.id)} actionIcon={<X size={11} />} onMarkAsRead={onMarkAsRead ? () => onMarkAsRead(p.id) : undefined} />)}
        </div>)}
        {tab === 'hot' && (<div className="p-3 space-y-1">
          {hotLoading ? <CL /> : hotPapers.length === 0 ? <Em text="No hot papers" sub="API may be offline" /> :
            hotPapers.map(p => <PC key={p.id} paper={p} onAction={() => readingListIds.has(p.id) ? onRemoveFromList(p.id) : onAddToList(p.id)}
              actionIcon={readingListIds.has(p.id) ? <X size={11} /> : <BookOpen size={11} />} highlight />)}
        </div>)}
        {tab === 'recs' && (<div className="p-3 space-y-1">
          {recsLoading ? <CL /> : recs.length === 0 ? <Em text="No recommendations" sub="Add papers to your reading list first" /> :
            recs.map(p => <PC key={p.id} paper={p} reason={(p as Recommendation).reason}
              onAction={() => readingListIds.has(p.id) ? onRemoveFromList(p.id) : onAddToList(p.id)}
              actionIcon={readingListIds.has(p.id) ? <X size={11} /> : <BookOpen size={11} />} />)}
        </div>)}
      </div>
    </div>
  );
}

function TB({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (<button onClick={onClick} className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-[11px] font-medium relative ${active ? 'text-gray-800' : 'text-gray-400 hover:text-gray-500'}`}>
    {icon} {label}{active && <div className="absolute bottom-0 left-2 right-2 h-[2px] bg-gray-800 rounded-full" />}</button>);
}
function PC({ paper, onAction, actionIcon, highlight, reason, onMarkAsRead }: { paper: Paper; onAction: () => void; actionIcon: React.ReactNode; highlight?: boolean; reason?: string; onMarkAsRead?: () => void }) {
  const arxiv = paper.id?.match(/^\d{4}\./) ? `https://arxiv.org/abs/${paper.id}` : null;
  return (<div className={`group p-2.5 rounded-lg border ${highlight ? 'border-amber-200 bg-amber-50/30 hover:bg-amber-50/60' : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50/50'}`}>
    <div className="flex items-start gap-1.5"><div className="flex-1 min-w-0">
      <p className="text-xs font-medium text-gray-700 leading-snug line-clamp-2">{paper.title}</p>
      <div className="flex items-center gap-1.5 mt-1">{paper.citation_count != null && <span className="text-[9px] text-gray-400">{fmtCit(paper.citation_count)}</span>}
        {paper.update_date && <span className="text-[9px] text-gray-400">{String(paper.update_date).slice(0, 4)}</span>}</div>
    </div>
    <div className="flex items-center gap-0.5 shrink-0">
      {arxiv && <a href={arxiv} target="_blank" rel="noopener noreferrer" className="p-1 rounded text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100"><ExternalLink size={10} /></a>}
      {onMarkAsRead && <button onClick={onMarkAsRead} className="p-1 rounded text-gray-300 hover:text-emerald-500 opacity-0 group-hover:opacity-100" title="Mark as read"><CheckCircle size={10} /></button>}
      <button onClick={onAction} className="p-1 rounded text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100">{actionIcon}</button>
    </div></div></div>);
}
function CL() { return <div className="py-8 flex justify-center"><Loader2 size={18} className="animate-spin text-gray-400" /></div>; }
function Em({ text, sub }: { text: string; sub: string }) { return <div className="flex flex-col items-center py-12 text-center"><p className="text-sm text-gray-400">{text}</p><p className="text-xs text-gray-300 mt-1">{sub}</p></div>; }

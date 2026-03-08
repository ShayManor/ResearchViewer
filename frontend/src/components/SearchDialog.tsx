import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, FileText, User, Loader2, SlidersHorizontal, Plus, Check } from 'lucide-react';
import { api, type Paper, type Author } from '../lib/api';
import { getCatColor, fmtCit } from '../lib/colors';

interface Props { onClose: () => void; onAddToList: (id: string) => void; readingListIds: Set<string>; }
type Tab = 'papers' | 'authors';

export function SearchDialog({ onClose, onAddToList, readingListIds }: Props) {
  const [tab, setTab] = useState<Tab>('papers');
  const [query, setQuery] = useState('');
  const [papers, setPapers] = useState<Paper[]>([]);
  const [pTotal, setPTotal] = useState(0);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [loading, setLoading] = useState(false);
  const [showF, setShowF] = useState(false);
  const [fSubject, setFSubject] = useState('');
  const [fAuthor, setFAuthor] = useState('');
  const [fStart, setFStart] = useState('');
  const [fEnd, setFEnd] = useState('');
  const [fMinCit, setFMinCit] = useState('');
  const [fSort, setFSort] = useState<string>('citation_count');
  const [fOrder, setFOrder] = useState<string>('DESC');
  const inputRef = useRef<HTMLInputElement>(null);
  const debRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => { inputRef.current?.focus(); const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [onClose]);

  const doSearch = useCallback(() => {
    const q = query.trim();
    if (!q && !fSubject && !fAuthor && !fMinCit) { setPapers([]); setAuthors([]); return; }
    setLoading(true);

    if (tab === 'papers') {
      api.getPapers({ keyword: q || undefined, subject: fSubject || undefined, author: fAuthor || undefined,
        start_date: fStart || undefined, end_date: fEnd || undefined, min_citations: fMinCit || undefined,
        sort_by: fSort, sort_order: fOrder, per_page: 25 })
        .then(d => { setPapers(d.papers); setPTotal(d.total); })
        .catch(() => setPapers([]))
        .finally(() => setLoading(false));
    } else {
      if (!q) { setAuthors([]); setLoading(false); return; }
      api.searchAuthors(q, 15).then(d => setAuthors(d.authors)).catch(() => setAuthors([])).finally(() => setLoading(false));
    }
  }, [tab, query, fSubject, fAuthor, fStart, fEnd, fMinCit, fSort, fOrder]);

  useEffect(() => { clearTimeout(debRef.current); debRef.current = setTimeout(doSearch, 350); }, [doSearch]);

  const hasF = fSubject || fAuthor || fStart || fEnd || fMinCit;
  const clearF = () => { setFSubject(''); setFAuthor(''); setFStart(''); setFEnd(''); setFMinCit(''); };

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-start justify-center pt-[10vh] px-4">
        <div className="w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up" onClick={e => e.stopPropagation()}>
          {/* Input */}
          <div className="flex items-center gap-3 px-5 border-b border-gray-100">
            <Search size={18} className="text-gray-400 shrink-0" />
            <input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)}
              placeholder={tab === 'papers' ? 'Search papers by title, author, DOI…' : 'Search authors…'}
              className="flex-1 py-4 text-sm text-gray-800 placeholder:text-gray-300 focus:outline-none bg-transparent" />
            {loading && <Loader2 size={16} className="text-gray-400 animate-spin" />}
            <button onClick={() => setShowF(!showF)} className={`p-1.5 rounded-lg transition-colors ${showF || hasF ? 'text-blue-500 bg-blue-50' : 'text-gray-400 hover:bg-gray-100'}`}><SlidersHorizontal size={15} /></button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"><X size={16} /></button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 px-5 py-2 bg-gray-50/50 border-b border-gray-100">
            <button onClick={() => { setTab('papers'); setPapers([]); }} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === 'papers' ? 'bg-white text-gray-800 shadow-sm border border-gray-200' : 'text-gray-400'}`}><FileText size={12} /> Papers</button>
            <button onClick={() => { setTab('authors'); setAuthors([]); }} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === 'authors' ? 'bg-white text-gray-800 shadow-sm border border-gray-200' : 'text-gray-400'}`}><User size={12} /> Authors</button>
          </div>

          {/* Filters */}
          {showF && tab === 'papers' && (
            <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/30 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Filters</span>
                {hasF && <button onClick={clearF} className="text-[10px] text-blue-500">Clear</button>}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <FIn label="Subject" value={fSubject} onChange={setFSubject} placeholder="cs.LG" />
                <FIn label="Author" value={fAuthor} onChange={setFAuthor} placeholder="Vaswani" />
                <FIn label="Min Citations" value={fMinCit} onChange={setFMinCit} placeholder="1000" />
              </div>
              <div className="grid grid-cols-4 gap-2">
                <FIn label="From" value={fStart} onChange={setFStart} type="date" />
                <FIn label="To" value={fEnd} onChange={setFEnd} type="date" />
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Sort</label><select value={fSort} onChange={e => setFSort(e.target.value)} className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none"><option value="citation_count">Citations</option><option value="update_date">Date</option><option value="title">Title</option></select></div>
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Order</label><select value={fOrder} onChange={e => setFOrder(e.target.value)} className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none"><option value="DESC">Desc</option><option value="ASC">Asc</option></select></div>
              </div>
            </div>
          )}

          {/* Results */}
          <div className="max-h-[45vh] overflow-y-auto">
            {tab === 'papers' && (
              <>
                {!query.trim() && !hasF && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">Type or add filters to search</p></div>}
                {(query.trim() || hasF) && !papers.length && !loading && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">No papers found</p></div>}
                {papers.map(p => {
                  const c = getCatColor(p.categories?.split(' ')[0] || '');
                  const inList = readingListIds.has(p.id);
                  return (
                    <div key={p.id} className="flex items-center px-5 py-3 hover:bg-gray-50 border-b border-gray-50 group">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center mt-0.5" style={{ backgroundColor: c.fill, border: `1px solid ${c.border}30` }}><FileText size={13} style={{ color: c.text }} /></div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-700 leading-snug line-clamp-2">{p.title}</p>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <span className="text-[10px] text-gray-400 font-mono">{p.id}</span>
                            {p.citation_count != null && <span className="text-[10px] text-gray-400">{fmtCit(p.citation_count)} cites</span>}
                            {p.categories && <span className="text-[10px] px-1.5 rounded-full" style={{ color: c.text, backgroundColor: c.fill }}>{p.categories.split(' ')[0]}</span>}
                            {p.update_date && <span className="text-[10px] text-gray-400">{String(p.update_date).slice(0, 4)}</span>}
                          </div>
                          {p.authors && <p className="text-[10px] text-gray-400 mt-0.5 truncate">{p.authors}</p>}
                        </div>
                      </div>
                      <button onClick={() => { if (!inList) onAddToList(p.id); }}
                        className={`p-2 rounded-lg shrink-0 ml-2 transition-all ${inList ? 'text-blue-500 bg-blue-50' : 'text-gray-300 hover:text-gray-600 hover:bg-gray-100 opacity-0 group-hover:opacity-100'}`}>
                        {inList ? <Check size={14} /> : <Plus size={14} />}
                      </button>
                    </div>
                  );
                })}
              </>
            )}
            {tab === 'authors' && (
              <>
                {!query.trim() && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">Search authors by name</p></div>}
                {query.trim() && !authors.length && !loading && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">No authors found</p></div>}
                {authors.map(a => (
                  <div key={a.author_id} className="px-5 py-3 hover:bg-gray-50 border-b border-gray-50">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center"><User size={14} className="text-gray-500" /></div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-700">{a.name}</p>
                        <div className="flex items-center gap-3 mt-0.5 text-[10px] text-gray-400">
                          {a.h_index != null && <span>h: <strong className="text-gray-600">{a.h_index}</strong></span>}
                          {a.works_count != null && <span>{a.works_count} papers</span>}
                          {a.cited_by_count != null && <span>{a.cited_by_count.toLocaleString()} cites</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="px-5 py-2.5 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <span className="text-[10px] text-gray-400"><kbd className="px-1 py-0.5 bg-white border border-gray-200 rounded font-mono">Esc</kbd> Close</span>
            {tab === 'papers' && pTotal > 0 && <span className="text-[10px] text-gray-400">{pTotal.toLocaleString()} results</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

function FIn({ label, value, onChange, placeholder, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string }) {
  return (
    <div>
      <label className="block text-[10px] text-gray-500 mb-0.5">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-gray-300 placeholder:text-gray-300" />
    </div>
  );
}

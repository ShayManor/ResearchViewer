import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, FileText, User, Loader2, SlidersHorizontal, Plus, Check } from 'lucide-react';
import { api, type Paper, type Author } from '../lib/api';
import { SEED_PAPERS } from '../lib/dummy-data';
import { getCategoryColor, getCategoryLabel, formatCitations } from '../lib/colors';

interface Props { onClose: () => void; onSelectPaper: (p: Paper) => void; onAddToList: (doi: string) => void; readingList: string[]; }
type Tab = 'papers' | 'authors';

export function SearchDialog({ onClose, onSelectPaper, onAddToList, readingList }: Props) {
  const [tab, setTab] = useState<Tab>('papers');
  const [query, setQuery] = useState('');
  const [papers, setPapers] = useState<Paper[]>([]);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [fSubject, setFSubject] = useState('');
  const [fStart, setFStart] = useState('');
  const [fEnd, setFEnd] = useState('');
  const [fSort, setFSort] = useState<'citation_count' | 'update_date'>('citation_count');
  const [fOrder, setFOrder] = useState<'DESC' | 'ASC'>('DESC');
  const [fMinCitations, setFMinCitations] = useState('');
  const [fMinHIndex, setFMinHIndex] = useState('');
  const [fMinWorks, setFMinWorks] = useState('');
  const [fOrg, setFOrg] = useState('');
  const [selectedAuthorId, setSelectedAuthorId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debRef = useRef<ReturnType<typeof setTimeout>>();
  const readSet = new Set(readingList);

  useEffect(() => { inputRef.current?.focus(); const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [onClose]);

  const doSearch = useCallback((q: string) => {
    if (!q.trim() && !fSubject && !fOrg) { setPapers([]); setAuthors([]); return; }
    setLoading(true);
    if (tab === 'papers') {
      const params: Record<string, string> = { per_page: '20', sort_by: fSort, sort_order: fOrder };
      if (q.trim()) params.keyword = q.trim();
      if (fSubject) params.subject = fSubject;
      if (fStart) params.start_date = fStart;
      if (fEnd) params.end_date = fEnd;
      const local = SEED_PAPERS.filter(p => {
        if (q.trim() && !p.title.toLowerCase().includes(q.toLowerCase()) && !p.authors?.toLowerCase().includes(q.toLowerCase()) && !p.doi.includes(q)) return false;
        if (fSubject && !(p.categories || '').toLowerCase().includes(fSubject.toLowerCase())) return false;
        if (fStart && (p.update_date || '') < fStart) return false;
        if (fEnd && (p.update_date || '') > fEnd) return false;
        return true;
      });
      api.getPapers(params).then(d => {
        const seen = new Set<string>(); const merged: Paper[] = [];
        for (const p of [...local, ...d.papers]) { if (!seen.has(p.doi)) { seen.add(p.doi); merged.push(p); } }
        merged.sort((a, b) => fSort === 'citation_count' ? ((b.citation_count || 0) - (a.citation_count || 0)) * (fOrder === 'DESC' ? 1 : -1) : ((b.update_date || '') > (a.update_date || '') ? 1 : -1) * (fOrder === 'DESC' ? 1 : -1));
        setPapers(merged.slice(0, 25));
      }).catch(() => { local.sort((a, b) => fSort === 'citation_count' ? ((b.citation_count || 0) - (a.citation_count || 0)) * (fOrder === 'DESC' ? 1 : -1) : ((b.update_date || '') > (a.update_date || '') ? 1 : -1) * (fOrder === 'DESC' ? 1 : -1)); setPapers(local); }).finally(() => setLoading(false));
    } else {
      if (!q.trim() && !fOrg) { setAuthors([]); setLoading(false); return; }
      api.searchAuthors(q || fOrg, 50).then(d => {
        let filtered = d.authors;
        const minCit = parseInt(fMinCitations);
        const minH = parseInt(fMinHIndex);
        const minW = parseInt(fMinWorks);
        if (!isNaN(minCit)) filtered = filtered.filter(a => (a.cited_by_count || 0) >= minCit);
        if (!isNaN(minH)) filtered = filtered.filter(a => (a.h_index || 0) >= minH);
        if (!isNaN(minW)) filtered = filtered.filter(a => (a.works_count || 0) >= minW);
        if (fOrg) filtered = filtered.filter(a => a.name.toLowerCase().includes(fOrg.toLowerCase()));
        setAuthors(filtered);
      }).catch(() => setAuthors([])).finally(() => setLoading(false));
    }
  }, [tab, fSubject, fStart, fEnd, fSort, fOrder, fMinCitations, fMinHIndex, fMinWorks, fOrg]);

  useEffect(() => { clearTimeout(debRef.current); debRef.current = setTimeout(() => doSearch(query), 300); }, [query, doSearch]);
  useEffect(() => { if (query || fSubject || fOrg) { clearTimeout(debRef.current); debRef.current = setTimeout(() => doSearch(query), 100); } }, [fSubject, fStart, fEnd, fSort, fOrder, fMinCitations, fMinHIndex, fMinWorks, fOrg]);

  useEffect(() => {
    if (selectedAuthorId) {
      setLoading(true);
      api.getAuthor(selectedAuthorId).then(author => {
        if (author.paper_dois && author.paper_dois.length > 0) {
          const fetchPapers = author.paper_dois.slice(0, 20).map(doi =>
            api.getPaper(doi).catch(() => null)
          );
          Promise.all(fetchPapers).then(results => {
            const validPapers = results.filter((p): p is Paper => p !== null);
            setPapers(validPapers);
            setTab('papers');
          }).finally(() => setLoading(false));
        } else {
          setPapers([]);
          setLoading(false);
        }
      }).catch(() => setLoading(false));
    }
  }, [selectedAuthorId]);

  const hasFilters = fSubject || fStart || fEnd || fMinCitations || fMinHIndex || fMinWorks || fOrg;

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-start justify-center pt-[10vh] px-4">
        <div className="w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up" onClick={e => e.stopPropagation()}>
          <div className="flex items-center gap-3 px-5 border-b border-gray-100">
            <Search size={18} className="text-gray-400 shrink-0" />
            <input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)}
              placeholder={tab === 'papers' ? 'Search papers by title, author, DOI…' : 'Search authors…'}
              className="flex-1 py-4 text-sm text-gray-800 placeholder:text-gray-300 focus:outline-none bg-transparent" />
            {loading && <Loader2 size={16} className="text-gray-400 animate-spin" />}
            <button onClick={() => setShowFilters(!showFilters)} className={`p-1.5 rounded-lg transition-colors ${showFilters || hasFilters ? 'text-blue-500 bg-blue-50' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}><SlidersHorizontal size={15} /></button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"><X size={16} /></button>
          </div>

          <div className="flex items-center gap-1 px-5 py-2 bg-gray-50/50 border-b border-gray-100">
            <button onClick={() => { setTab('papers'); setPapers([]); setAuthors([]); setSelectedAuthorId(null); }} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === 'papers' ? 'bg-white text-gray-800 shadow-sm border border-gray-200' : 'text-gray-400 hover:text-gray-500'}`}><FileText size={12} /> Papers</button>
            <button onClick={() => { setTab('authors'); setPapers([]); setAuthors([]); setSelectedAuthorId(null); }} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === 'authors' ? 'bg-white text-gray-800 shadow-sm border border-gray-200' : 'text-gray-400 hover:text-gray-500'}`}><User size={12} /> Authors</button>
            {selectedAuthorId && <span className="text-xs text-gray-400 ml-2">Viewing papers by selected author</span>}
          </div>

          {showFilters && tab === 'papers' && (
            <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/30 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Filters</span>
                {hasFilters && <button onClick={() => { setFSubject(''); setFStart(''); setFEnd(''); }} className="text-[10px] text-blue-500 hover:text-blue-600">Clear</button>}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Subject</label><input type="text" value={fSubject} onChange={e => setFSubject(e.target.value)} placeholder="cs.LG" className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-gray-300 placeholder:text-gray-300" /></div>
                <div><label className="block text-[10px] text-gray-500 mb-0.5">From</label><input type="date" value={fStart} onChange={e => setFStart(e.target.value)} className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-gray-300" /></div>
                <div><label className="block text-[10px] text-gray-500 mb-0.5">To</label><input type="date" value={fEnd} onChange={e => setFEnd(e.target.value)} className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-gray-300" /></div>
              </div>
              <div className="flex gap-2">
                <div className="flex-1"><label className="block text-[10px] text-gray-500 mb-0.5">Sort</label><select value={fSort} onChange={e => setFSort(e.target.value as any)} className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none"><option value="citation_count">Citations</option><option value="update_date">Date</option></select></div>
                <div className="flex-1"><label className="block text-[10px] text-gray-500 mb-0.5">Order</label><select value={fOrder} onChange={e => setFOrder(e.target.value as any)} className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none"><option value="DESC">Desc</option><option value="ASC">Asc</option></select></div>
              </div>
            </div>
          )}

          {showFilters && tab === 'authors' && (
            <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/30 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Filters</span>
                {hasFilters && <button onClick={() => { setFMinCitations(''); setFMinHIndex(''); setFMinWorks(''); setFOrg(''); }} className="text-[10px] text-blue-500 hover:text-blue-600">Clear</button>}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Organization <span className="text-gray-300">(in name)</span></label><input type="text" value={fOrg} onChange={e => setFOrg(e.target.value)} placeholder="Stanford, MIT, etc." className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-300 placeholder:text-gray-300" /></div>
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Min Citations</label><input type="number" value={fMinCitations} onChange={e => setFMinCitations(e.target.value)} placeholder="1000" className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-300 placeholder:text-gray-300" /></div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Min h-index</label><input type="number" value={fMinHIndex} onChange={e => setFMinHIndex(e.target.value)} placeholder="20" className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-300 placeholder:text-gray-300" /></div>
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Min Papers</label><input type="number" value={fMinWorks} onChange={e => setFMinWorks(e.target.value)} placeholder="50" className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-300 placeholder:text-gray-300" /></div>
              </div>
            </div>
          )}

          <div className="max-h-[45vh] overflow-y-auto">
            {tab === 'papers' && (
              <>
                {!query && !fSubject && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">Type or add filters to search</p></div>}
                {(query || fSubject) && !papers.length && !loading && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">No papers found</p></div>}
                {papers.map(p => {
                  const c = getCategoryColor(p.categories?.split(' ')[0] || '');
                  const inList = readSet.has(p.doi);
                  return (
                    <div key={p.doi} className="flex items-center px-5 py-3 hover:bg-gray-50 border-b border-gray-50 transition-colors group">
                      <button onClick={() => onSelectPaper(p)} className="flex items-start gap-3 flex-1 min-w-0 text-left">
                        <div className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center mt-0.5" style={{ backgroundColor: c.fill, border: `1px solid ${c.border}30` }}><FileText size={13} style={{ color: c.text }} /></div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-700 group-hover:text-gray-900 leading-snug line-clamp-2">{p.title}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-gray-400 font-mono">{p.doi}</span>
                            {p.citation_count != null && <span className="text-[10px] text-gray-400">{formatCitations(p.citation_count)}</span>}
                            {p.categories && <span className="text-[10px] px-1.5 py-0 rounded-full" style={{ color: c.text, backgroundColor: c.fill }}>{getCategoryLabel(p.categories.split(' ')[0])}</span>}
                          </div>
                          {p.authors && <p className="text-[10px] text-gray-400 mt-0.5 truncate">{p.authors}</p>}
                        </div>
                      </button>
                      <button onClick={e => { e.stopPropagation(); if (!inList) onAddToList(p.doi); }}
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
                {!query && !fOrg && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">Search authors by name or use filters</p></div>}
                {(query || fOrg) && !authors.length && !loading && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">No authors found</p></div>}
                {authors.map(a => (
                  <button
                    key={a.author_id}
                    onClick={() => setSelectedAuthorId(a.author_id)}
                    className="w-full px-5 py-3 hover:bg-blue-50 border-b border-gray-50 transition-colors group text-left"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center group-hover:from-blue-200 group-hover:to-blue-300 transition-all"><User size={14} className="text-blue-600" /></div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-700 group-hover:text-blue-600 transition-colors">{a.name}</p>
                        <div className="flex items-center gap-3 mt-0.5 text-[10px] text-gray-400">
                          {a.h_index != null && <span>h-index: <strong className="text-gray-600">{a.h_index}</strong></span>}
                          {a.works_count != null && <span><strong className="text-gray-600">{a.works_count}</strong> papers</span>}
                          {a.cited_by_count != null && <span><strong className="text-gray-600">{a.cited_by_count.toLocaleString()}</strong> cites</span>}
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </>
            )}
          </div>

          <div className="px-5 py-2.5 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <span className="text-[10px] text-gray-400"><kbd className="px-1 py-0.5 bg-white border border-gray-200 rounded font-mono">Esc</kbd> Close</span>
            {tab === 'papers' && papers.length > 0 && <span className="text-[10px] text-gray-400">{papers.length} results</span>}
            {tab === 'authors' && authors.length > 0 && <span className="text-[10px] text-gray-400">{authors.length} results • Click to view papers</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

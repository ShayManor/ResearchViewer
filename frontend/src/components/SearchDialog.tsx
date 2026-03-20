import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, FileText, User, Loader2, SlidersHorizontal, Plus, Check, ExternalLink, CheckCircle, BookOpen } from 'lucide-react';
import { api, type Paper, type Author, type DomainEntry, type TopicEntry, type Microtopic } from '../lib/api';
import { getCatColor, fmtCit } from '../lib/colors';

interface Props {
  onClose: () => void;
  onAddToList: (id: string) => void;
  onMarkAsRead: (id: string) => void;
  readingListIds: Set<string>;
}
type Tab = 'papers' | 'authors';

export function SearchDialog({ onClose, onAddToList, onMarkAsRead, readingListIds }: Props) {
  const [tab, setTab] = useState<Tab>('papers');
  const [query, setQuery] = useState('');
  const [papers, setPapers] = useState<Paper[]>([]);
  const [pTotal, setPTotal] = useState(0);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [loading, setLoading] = useState(false);
  const [showF, setShowF] = useState(false);

  // Cascading filters: domain → topic → microtopic
  const [domains, setDomains] = useState<DomainEntry[]>([]);
  const [fDomain, setFDomain] = useState('');
  const [topics, setTopics] = useState<TopicEntry[]>([]);
  const [fTopic, setFTopic] = useState('');
  const [microtopics, setMicrotopics] = useState<Microtopic[]>([]);
  const [fMicrotopic, setFMicrotopic] = useState('');

  // Other filters
  const [fAuthor, setFAuthor] = useState('');
  const [fStart, setFStart] = useState('');
  const [fEnd, setFEnd] = useState('');
  const [fMinCit, setFMinCit] = useState('');
  const [fSort, setFSort] = useState('citation_count');
  const [fOrder, setFOrder] = useState('DESC');

  const inputRef = useRef<HTMLInputElement>(null);
  const debRef = useRef<ReturnType<typeof setTimeout>>();

  // Load domains on mount
  useEffect(() => {
    api.getDomains(100).then(d => setDomains(d.domains)).catch(() => {});
  }, []);

  // Load topics when domain changes
  useEffect(() => {
    if (!fDomain) {
      setTopics([]);
      setFTopic('');
      setMicrotopics([]);
      setFMicrotopic('');
      return;
    }
    api.getTopicsInDomain(fDomain, 100).then(d => setTopics(d.topics)).catch(() => setTopics([]));
    setFTopic('');
    setMicrotopics([]);
    setFMicrotopic('');
  }, [fDomain]);

  // Load microtopics when topic changes
  useEffect(() => {
    if (!fTopic) {
      setMicrotopics([]);
      setFMicrotopic('');
      return;
    }
    api.getMicrotopics({ bucket_value: fTopic, limit: 100 }).then(d => setMicrotopics(d.microtopics)).catch(() => setMicrotopics([]));
    setFMicrotopic('');
  }, [fTopic]);

  const doSearch = useCallback(() => {
    const q = query.trim();
    // Search if there's a query OR any filter
    if (!q && !fDomain && !fTopic && !fMicrotopic && !fAuthor && !fMinCit && !fStart && !fEnd) {
      setPapers([]); setPTotal(0); setAuthors([]);
      return;
    }
    setLoading(true);

    if (tab === 'papers') {
      const params: Record<string, string> = { per_page: '25', sort_by: fSort, sort_order: fOrder };
      if (q) params.keyword = q;
      if (fDomain) params.domain = fDomain;
      if (fTopic) params.topic = fTopic;
      if (fMicrotopic) params.microtopic_id = fMicrotopic;
      if (fAuthor) params.author = fAuthor;
      if (fStart) params.start_date = fStart;
      if (fEnd) params.end_date = fEnd;
      if (fMinCit) params.min_citations = fMinCit;

      api.getPapers(params)
        .then(d => { setPapers(d.papers); setPTotal(d.total); })
        .catch(() => { setPapers([]); setPTotal(0); })
        .finally(() => setLoading(false));
    } else {
      if (!q) { setAuthors([]); setLoading(false); return; }
      api.searchAuthors(q, 15)
        .then(d => setAuthors(d.authors))
        .catch(() => setAuthors([]))
        .finally(() => setLoading(false));
    }
  }, [tab, query, fDomain, fTopic, fMicrotopic, fAuthor, fStart, fEnd, fMinCit, fSort, fOrder]);

  // Focus input and handle keyboard shortcuts
  useEffect(() => {
    inputRef.current?.focus();
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      // Trigger search immediately on Enter key
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        clearTimeout(debRef.current);
        doSearch();
      }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose, doSearch]);

  // Debounced search on any input change (longer delay to avoid slow searches on every keystroke)
  useEffect(() => {
    clearTimeout(debRef.current);
    debRef.current = setTimeout(doSearch, 800);
    return () => clearTimeout(debRef.current);
  }, [doSearch]);

  const hasF = !!(fDomain || fTopic || fMicrotopic || fAuthor || fStart || fEnd || fMinCit);
  const clearF = () => {
    setFDomain(''); setFTopic(''); setFMicrotopic('');
    setFAuthor(''); setFStart(''); setFEnd(''); setFMinCit('');
    setTopics([]); setMicrotopics([]);
  };
  const noInput = !query.trim() && !hasF;

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-start justify-center pt-[10vh] px-4">
        <div className="w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up" onClick={e => e.stopPropagation()}>

          {/* Search input */}
          <div className="flex items-center gap-3 px-5 border-b border-gray-100">
            <Search size={18} className="text-gray-400 shrink-0" />
            <input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)}
              placeholder={tab === 'papers' ? 'Search papers by title, author, abstract…' : 'Search authors by name…'}
              className="flex-1 py-4 text-sm text-gray-800 placeholder:text-gray-300 focus:outline-none bg-transparent" />
            {loading && <Loader2 size={16} className="text-gray-400 animate-spin" />}
            {tab === 'papers' && (
              <button onClick={() => setShowF(!showF)}
                className={`p-1.5 rounded-lg transition-colors ${showF || hasF ? 'text-blue-500 bg-blue-50' : 'text-gray-400 hover:bg-gray-100'}`}>
                <SlidersHorizontal size={15} />
              </button>
            )}
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"><X size={16} /></button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 px-5 py-2 bg-gray-50/50 border-b border-gray-100">
            <button onClick={() => { setTab('papers'); setAuthors([]); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === 'papers' ? 'bg-white text-gray-800 shadow-sm border border-gray-200' : 'text-gray-400'}`}>
              <FileText size={12} /> Papers
            </button>
            <button onClick={() => { setTab('authors'); setPapers([]); setPTotal(0); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === 'authors' ? 'bg-white text-gray-800 shadow-sm border border-gray-200' : 'text-gray-400'}`}>
              <User size={12} /> Authors
            </button>
          </div>

          {/* Filters */}
          {showF && tab === 'papers' && (
            <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/30 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Filters</span>
                {hasF && <button onClick={clearF} className="text-[10px] text-blue-500">Clear</button>}
              </div>

              {/* Cascading Dropdowns: Domain → Topic → Microtopic */}
              <div className="grid grid-cols-3 gap-2">
                {/* Domain */}
                <div>
                  <label className="block text-[10px] text-gray-500 mb-0.5">Domain</label>
                  <select value={fDomain} onChange={e => setFDomain(e.target.value)}
                    className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none">
                    <option value="">All domains</option>
                    {domains.map(d => (
                      <option key={d.domain} value={d.domain}>{d.domain}</option>
                    ))}
                  </select>
                </div>

                {/* Topic */}
                <div>
                  <label className="block text-[10px] text-gray-500 mb-0.5">Topic</label>
                  {!fDomain ? (
                    <select disabled className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-gray-100 text-gray-400">
                      <option>Select domain first</option>
                    </select>
                  ) : (
                    <select value={fTopic} onChange={e => setFTopic(e.target.value)}
                      className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none">
                      <option value="">All topics</option>
                      {topics.map(t => (
                        <option key={t.topic} value={t.topic}>{t.topic}</option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Microtopic */}
                <div>
                  <label className="block text-[10px] text-gray-500 mb-0.5">Microtopic</label>
                  {!fTopic ? (
                    <select disabled className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-gray-100 text-gray-400">
                      <option>Select topic first</option>
                    </select>
                  ) : (
                    <select value={fMicrotopic} onChange={e => setFMicrotopic(e.target.value)}
                      className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none">
                      <option value="">All microtopics</option>
                      {microtopics.map(m => (
                        <option key={m.microtopic_id} value={m.microtopic_id}>{m.label}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {/* Other Filters */}
              <div className="grid grid-cols-4 gap-2">
                <FIn label="Author" value={fAuthor} onChange={setFAuthor} placeholder="Vaswani" />
                <FIn label="Min Citations" value={fMinCit} onChange={setFMinCit} placeholder="1000" />
                <FIn label="From" value={fStart} onChange={setFStart} type="date" />
                <FIn label="To" value={fEnd} onChange={setFEnd} type="date" />
              </div>

              {/* Sort Options */}
              <div className="grid grid-cols-2 gap-2">
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Sort</label>
                  <select value={fSort} onChange={e => setFSort(e.target.value)} className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none">
                    <option value="citation_count">Citations</option><option value="update_date">Date</option><option value="title">Title</option>
                  </select>
                </div>
                <div><label className="block text-[10px] text-gray-500 mb-0.5">Order</label>
                  <select value={fOrder} onChange={e => setFOrder(e.target.value)} className="w-full px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none">
                    <option value="DESC">Desc</option><option value="ASC">Asc</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* Results */}
          <div className="max-h-[45vh] overflow-y-auto">
            {tab === 'papers' && (
              <>
                {noInput && !loading && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">Type a query or add filters to search</p><p className="text-xs text-gray-300 mt-1">Press Enter to search immediately</p></div>}
                {!noInput && !papers.length && !loading && <div className="px-5 py-8 text-center"><p className="text-sm text-gray-400">No papers found</p></div>}
                {papers.map(p => {
                  const c = getCatColor(p.categories?.split(' ')[0] || '');
                  const inList = readingListIds.has(p.id);
                  const arxiv = p.id?.match(/^\d{4}\./) ? `https://arxiv.org/abs/${p.id}` : null;

                  return (
                    <div key={p.id} className="px-5 py-3 hover:bg-gray-50 border-b border-gray-50 group">
                      <div className="flex items-start gap-3">
                        <div className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center mt-0.5" style={{ backgroundColor: c.fill, border: `1px solid ${c.border}30` }}>
                          <FileText size={13} style={{ color: c.text }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-700 leading-snug line-clamp-2">{p.title}</p>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <span className="text-[10px] text-gray-400 font-mono">{p.id}</span>
                            {p.citation_count != null && <span className="text-[10px] text-gray-400">{fmtCit(p.citation_count)} cites</span>}
                            {p.primary_topic_name && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-200">
                                {p.primary_topic_name}
                              </span>
                            )}
                            {p.update_date && <span className="text-[10px] text-gray-400">{String(p.update_date).slice(0, 4)}</span>}
                          </div>
                          {p.authors && <p className="text-[10px] text-gray-400 mt-0.5 truncate">{p.authors}</p>}

                          {/* Action buttons */}
                          <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (!inList) onAddToList(p.id);
                              }}
                              className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                                inList
                                  ? 'bg-blue-100 text-blue-600 cursor-default'
                                  : 'bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-600'
                              }`}
                              title="Add to reading list"
                            >
                              {inList ? <Check size={10} /> : <BookOpen size={10} />}
                              <span>{inList ? 'In list' : 'Add to list'}</span>
                            </button>

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onMarkAsRead(p.id);
                              }}
                              className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium bg-gray-100 text-gray-600 hover:bg-emerald-100 hover:text-emerald-600 transition-colors"
                              title="Mark as read"
                            >
                              <CheckCircle size={10} />
                              <span>Mark read</span>
                            </button>

                            {arxiv && (
                              <a
                                href={arxiv}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
                                title="Open on arXiv"
                              >
                                <ExternalLink size={10} />
                                <span>arXiv</span>
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
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

          {/* Footer */}
          <div className="px-5 py-2.5 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <span className="text-[10px] text-gray-400"><kbd className="px-1 py-0.5 bg-white border border-gray-200 rounded font-mono">Esc</kbd> Close</span>
            {tab === 'papers' && pTotal > 0 && <span className="text-[10px] text-gray-400">{pTotal.toLocaleString()} total results</span>}
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

import { useState, useEffect } from 'react';
import { X, BookOpen, TrendingUp, User, Link2, Unlink, Plus, FileText, BarChart3, Loader2 } from 'lucide-react';
import { getCatColor, fmtCit } from '../lib/colors';
import { api, type UserProfile, type Publication } from '../lib/api';

interface Props { userId: number; onClose: () => void; }

export function UserProfilePanel({ userId, onClose }: Props) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [pubs, setPubs] = useState<Publication[]>([]);
  const [pubTotal, setPubTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'reading' | 'publications' | 'settings'>('reading');

  // Author linking
  const [authorQ, setAuthorQ] = useState('');
  const [authorResults, setAuthorResults] = useState<{ author_id: string; name: string; h_index?: number; works_count?: number }[]>([]);
  const [searching, setSearching] = useState(false);

  // Add publication form
  const [pubTitle, setPubTitle] = useState('');
  const [pubVenue, setPubVenue] = useState('');
  const [pubYear, setPubYear] = useState(new Date().getFullYear());

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getUser(userId),
      api.getPublications(userId),
    ]).then(([u, p]) => {
      setProfile(u);
      setPubs(p.publications);
      setPubTotal(p.total_citations);
    }).catch(() => {})
      .finally(() => setLoading(false));
  }, [userId]);

  const doSearchAuthor = async () => {
    if (!authorQ.trim()) return;
    setSearching(true);
    try { const r = await api.searchAuthors(authorQ, 5); setAuthorResults(r.authors); }
    catch { setAuthorResults([]); }
    setSearching(false);
  };

  const doLinkAuthor = async (authorId: string) => {
    try {
      const r = await api.linkAuthor(userId, authorId);
      setProfile(prev => prev ? { ...prev, linked_author_id: authorId, linked_author_name: r.author_name } : prev);
      setAuthorResults([]); setAuthorQ('');
    } catch {}
  };

  const doUnlink = async () => {
    try {
      await api.unlinkAuthor(userId);
      setProfile(prev => prev ? { ...prev, linked_author_id: undefined, linked_author_name: undefined } : prev);
    } catch {}
  };

  const doAddPub = async () => {
    if (!pubTitle.trim()) return;
    try {
      await api.addPublication(userId, { title: pubTitle, venue: pubVenue, year: pubYear });
      const p = await api.getPublications(userId);
      setPubs(p.publications); setPubTotal(p.total_citations);
      setPubTitle(''); setPubVenue('');
    } catch {}
  };

  const doDeletePub = async (pubId: number) => {
    try {
      await api.deletePublication(userId, pubId);
      setPubs(prev => prev.filter(p => p.id !== pubId));
    } catch {}
  };

  if (loading || !profile) {
    return (
      <div className="fixed inset-0 z-50">
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
        <div className="fixed inset-0 flex items-center justify-center"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
      </div>
    );
  }

  const st = profile.stats;

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
          {/* Header */}
          <div className="px-6 py-5 border-b border-gray-100 shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gray-800 flex items-center justify-center text-xl font-bold text-white font-serif">{profile.username[0].toUpperCase()}</div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-800">{profile.username}</h2>
                  <p className="text-xs text-gray-400">{profile.email} · Joined {profile.created_at?.slice(0, 10)}</p>
                  {profile.linked_author_name && (
                    <div className="flex items-center gap-1.5 mt-1"><Link2 size={10} className="text-blue-500" /><span className="text-[10px] text-blue-600 font-medium">Linked to {profile.linked_author_name}</span></div>
                  )}
                </div>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"><X size={18} /></button>
            </div>

            {/* Summary metrics */}
            <div className="grid grid-cols-5 gap-2 mt-4">
              <PM label="Read" value={String(st.papers_read_count)} icon={<BookOpen size={11} />} />
              <PM label="Cites Covered" value={fmtCit(st.total_citations_covered)} icon={<TrendingUp size={11} />} />
              <PM label="Avg/Paper" value={fmtCit(st.avg_citations_per_read)} icon={<BarChart3 size={11} />} />
              <PM label="Pace" value={`${st.reading_pace_per_week}/wk`} icon={<TrendingUp size={11} />} />
              <PM label="Published" value={String(st.publication_count)} icon={<FileText size={11} />} />
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mt-4">
              {(['reading', 'publications', 'settings'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)} className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all capitalize ${tab === t ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>{t}</button>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {tab === 'reading' && (
              <div className="space-y-6">
                {/* By topic */}
                {profile.reading_by_topic.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Papers Read by Topic</p>
                    <div className="space-y-2">
                      {profile.reading_by_topic.map(({ topic, count }) => {
                        const cat = getCatColor(topic);
                        const pct = st.papers_read_count > 0 ? (count / st.papers_read_count) * 100 : 0;
                        return (
                          <div key={topic} className="flex items-center gap-2">
                            <span className="w-14 text-right text-[10px] font-medium shrink-0" style={{ color: cat.text }}>{topic}</span>
                            <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden"><div className="h-full rounded" style={{ width: `${pct}%`, backgroundColor: cat.border }} /></div>
                            <span className="w-8 text-right text-xs text-gray-600 font-mono font-medium">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Over time */}
                {profile.reading_over_time.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Reading Over Time</p>
                    <div className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                      <div className="flex items-end gap-1 h-16">
                        {profile.reading_over_time.map(({ month, count }, i) => {
                          const max = Math.max(...profile.reading_over_time.map(m => m.count), 1);
                          return (
                            <div key={month} className="flex-1 flex flex-col items-center gap-0.5" title={`${month}: ${count}`}>
                              <span className="text-[7px] text-gray-400 font-mono">{count}</span>
                              <div className="w-full rounded-t" style={{ height: `${(count / max) * 100}%`, minHeight: 2, backgroundColor: i === profile.reading_over_time.length - 1 ? '#3b82f6' : '#94a3b8' }} />
                            </div>
                          );
                        })}
                      </div>
                      <div className="flex justify-between mt-1.5 text-[8px] text-gray-400 font-mono">
                        <span>{profile.reading_over_time[0]?.month}</span>
                        <span>{profile.reading_over_time[profile.reading_over_time.length - 1]?.month}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Focus */}
                {profile.focus_topics.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Focus Areas</p>
                    <div className="flex flex-wrap gap-1.5">
                      {profile.focus_topics.map(t => { const cat = getCatColor(t); return <span key={t} className="px-2.5 py-1 rounded-full text-xs font-medium border" style={{ backgroundColor: cat.fill, color: cat.text, borderColor: cat.border + '40' }}>{t}</span>; })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {tab === 'publications' && (
              <div className="space-y-6">
                {/* Stats */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center"><p className="text-[8px] text-gray-400 uppercase">Published</p><p className="text-xl font-bold text-gray-800 font-mono">{pubs.length}</p></div>
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center"><p className="text-[8px] text-gray-400 uppercase">Total Cites</p><p className="text-xl font-bold text-gray-800 font-mono">{pubTotal}</p></div>
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center"><p className="text-[8px] text-gray-400 uppercase">Days Active</p><p className="text-xl font-bold text-gray-800 font-mono">{st.days_since_join}</p></div>
                </div>

                {/* Link author */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Linked Author</p>
                  {profile.linked_author_id ? (
                    <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 border border-blue-200">
                      <div className="flex items-center gap-2"><User size={16} className="text-blue-500" /><div><p className="text-sm font-medium text-blue-800">{profile.linked_author_name}</p><p className="text-[10px] text-blue-500 font-mono">{profile.linked_author_id}</p></div></div>
                      <button onClick={doUnlink} className="p-1.5 rounded-lg text-blue-400 hover:text-blue-600 hover:bg-blue-100"><Unlink size={14} /></button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-xs text-gray-500">Link your author profile to track publications.</p>
                      <div className="flex gap-2">
                        <input type="text" value={authorQ} onChange={e => setAuthorQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearchAuthor()} placeholder="Search by name…" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none placeholder:text-gray-300" />
                        <button onClick={doSearchAuthor} disabled={searching} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium disabled:opacity-50">
                          {searching ? <Loader2 size={14} className="animate-spin" /> : 'Search'}
                        </button>
                      </div>
                      {authorResults.length > 0 && <div className="space-y-1">
                        {authorResults.map(a => (
                          <button key={a.author_id} onClick={() => doLinkAuthor(a.author_id)} className="w-full flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-left">
                            <User size={14} className="text-gray-400 shrink-0" />
                            <div className="flex-1 min-w-0"><p className="text-sm font-medium text-gray-700">{a.name}</p>
                              <div className="flex gap-3 text-[10px] text-gray-400">{a.h_index != null && <span>h: {a.h_index}</span>}{a.works_count != null && <span>{a.works_count} papers</span>}</div>
                            </div>
                            <Link2 size={12} className="text-gray-300 shrink-0" />
                          </button>
                        ))}
                      </div>}
                    </div>
                  )}
                </div>

                {/* Publication list */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Your Publications</p>
                  {pubs.length > 0 ? <div className="space-y-2">
                    {pubs.map(p => (
                      <div key={p.id} className="group p-3 rounded-xl border border-gray-200 hover:bg-gray-50">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-medium text-gray-700">{p.title}</p>
                            <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-400">
                              {p.venue && <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium">{p.venue}</span>}
                              <span>{p.year}</span>
                              <span>{p.citation_count} cites</span>
                            </div>
                          </div>
                          <button onClick={() => doDeletePub(p.id)} className="p-1 rounded text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100"><X size={12} /></button>
                        </div>
                      </div>
                    ))}
                  </div> : <p className="text-xs text-gray-400 italic">No publications yet</p>}
                </div>

                {/* Add form */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Add Publication</p>
                  <div className="space-y-2">
                    <input type="text" value={pubTitle} onChange={e => setPubTitle(e.target.value)} placeholder="Title" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none placeholder:text-gray-300" />
                    <div className="flex gap-2">
                      <input type="text" value={pubVenue} onChange={e => setPubVenue(e.target.value)} placeholder="Venue" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none placeholder:text-gray-300" />
                      <input type="number" value={pubYear} onChange={e => setPubYear(parseInt(e.target.value))} className="w-20 px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none" />
                    </div>
                    <button onClick={doAddPub} disabled={!pubTitle.trim()} className="w-full py-2.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium disabled:opacity-40 flex items-center justify-center gap-1.5"><Plus size={14} /> Add Publication</button>
                  </div>
                </div>
              </div>
            )}

            {tab === 'settings' && (
              <div className="space-y-6">
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Account</p>
                  <div className="space-y-3">
                    <Row label="Username" value={profile.username} />
                    <Row label="Email" value={profile.email} />
                    <Row label="Member Since" value={`${profile.created_at?.slice(0, 10)} (${st.days_since_join} days)`} />
                    <Row label="Linked Author" value={profile.linked_author_name || 'None'} />
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Data Summary</p>
                  <div className="p-3 rounded-xl border border-gray-200 space-y-2 text-xs">
                    <div className="flex justify-between"><span className="text-gray-500">Reading list</span><span className="font-mono text-gray-700">{st.reading_list_count}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Papers read</span><span className="font-mono text-gray-700">{st.papers_read_count}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Publications</span><span className="font-mono text-gray-700">{st.publication_count}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Pub citations</span><span className="font-mono text-gray-700">{st.publication_citations}</span></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PM({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="p-2 rounded-lg bg-gray-50 border border-gray-100 text-center">
      <div className="flex items-center justify-center gap-1 text-gray-400 mb-0.5">{icon}<span className="text-[7px] uppercase tracking-wider">{label}</span></div>
      <p className="text-sm font-bold text-gray-800 font-mono tabular-nums">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-xl border border-gray-200">
      <p className="text-sm font-medium text-gray-700">{label}</p>
      <p className="text-xs text-gray-400">{value}</p>
    </div>
  );
}

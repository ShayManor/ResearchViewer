import { useState, useEffect, useMemo } from 'react';
import { X, BookOpen, TrendingUp, User, Link2, Unlink, Plus, FileText, BarChart3, Loader2, ChevronDown, LogOut, Trash2 } from 'lucide-react';
import { getCatColor, fmtCit } from '../lib/colors';
import { api, type UserProfile, type Publication } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

interface Props { userId: number; onClose: () => void; }

export function UserProfilePanel({ userId, onClose }: Props) {
  const { signOut } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [pubs, setPubs] = useState<Publication[]>([]);
  const [pubCites, setPubCites] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'reading' | 'publications' | 'settings'>('reading');
  const [authorQ, setAuthorQ] = useState('');
  const [authorRes, setAuthorRes] = useState<{ author_id: string; name: string; h_index?: number; works_count?: number }[]>([]);
  const [searching, setSearching] = useState(false);
  const [linking, setLinking] = useState(false);
  const [pubTitle, setPubTitle] = useState('');
  const [pubVenue, setPubVenue] = useState('');
  const [pubYear, setPubYear] = useState(new Date().getFullYear());
  const [selectedDomain, setSelectedDomain] = useState<string>('all');
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([api.getUser(userId), api.getPublications(userId)])
      .then(([u, p]) => { setProfile(u); setPubs(p.publications); setPubCites(p.total_citations); })
      .catch(() => {}).finally(() => setLoading(false));
  }, [userId]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  // Organize reading data by domain -> topic -> microtopics
  const readingByDomainAndTopic = useMemo(() => {
    if (!profile?.reading_by_microtopic) return { domains: [], byDomain: {} };

    const byDomain: Record<string, Record<string, typeof profile.reading_by_microtopic>> = {};
    const domains = new Set<string>();

    profile.reading_by_microtopic.forEach((item) => {
      domains.add(item.domain);
      if (!byDomain[item.domain]) byDomain[item.domain] = {};
      if (!byDomain[item.domain][item.topic]) byDomain[item.domain][item.topic] = [];
      byDomain[item.domain][item.topic].push(item);
    });

    return { domains: Array.from(domains).sort(), byDomain };
  }, [profile?.reading_by_microtopic]);

  const searchAuthor = async () => {
    if (!authorQ.trim()) return;
    setSearching(true);
    try { const r = await api.searchAuthors(authorQ, 5); setAuthorRes(r.authors); } catch { setAuthorRes([]); }
    setSearching(false);
  };
  const linkAuthor = async (aid: string) => {
    setLinking(true);
    try {
      const r = await api.linkAuthor(userId, aid);
      if (r.message) {
        alert(r.message);
      }
      const [u, p] = await Promise.all([api.getUser(userId), api.getPublications(userId)]);
      setProfile(u);
      setPubs(p.publications);
      setPubCites(p.total_citations);
      setAuthorRes([]);
      setAuthorQ('');
    } catch {
      alert('Failed to link author. Please try again.');
    } finally {
      setLinking(false);
    }
  };
  const unlinkAuthor = async () => {
    try {
      await api.unlinkAuthor(userId);
      const [u, p] = await Promise.all([api.getUser(userId), api.getPublications(userId)]);
      setProfile(u);
      setPubs(p.publications);
      setPubCites(p.total_citations);
    } catch {
      alert('Failed to unlink author. Please try again.');
    }
  };
  const addPub = async () => {
    if (!pubTitle.trim()) return;
    try { await api.addPublication(userId, { title: pubTitle, venue: pubVenue, year: pubYear }); const p = await api.getPublications(userId); setPubs(p.publications); setPubCites(p.total_citations); setPubTitle(''); setPubVenue(''); } catch {}
  };
  const delPub = async (id: number) => {
    try { await api.deletePublication(userId, id); setPubs(p => p.filter(x => x.id !== id)); } catch {}
  };

  const handleLogout = async () => {
    try {
      await signOut();
      onClose();
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== 'DELETE') {
      return;
    }

    setDeleting(true);
    try {
      await api.deleteAccount(userId);
      await signOut();
      onClose();
    } catch (err) {
      alert('Failed to delete account. Please try again or contact support.');
      setDeleting(false);
    }
  };

  if (loading || !profile) return (
    <div className="fixed inset-0 z-50"><div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-center justify-center"><Loader2 size={24} className="animate-spin text-gray-400" /></div></div>
  );

  const st = profile.stats;
  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
          <div className="px-6 py-5 border-b border-gray-100 shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gray-800 flex items-center justify-center text-xl font-bold text-white font-serif">{profile.username[0].toUpperCase()}</div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-800">{profile.username}</h2>
                  <p className="text-xs text-gray-400">{profile.email} · Joined {profile.created_at?.slice(0, 10)}</p>
                  {profile.linked_author_name && <div className="flex items-center gap-1.5 mt-1"><Link2 size={10} className="text-blue-500" /><span className="text-[10px] text-blue-600 font-medium">{profile.linked_author_name}</span></div>}
                </div>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"><X size={18} /></button>
            </div>
            <div className="grid grid-cols-5 gap-2 mt-4">
              <PM label="Read" value={String(st.papers_read_count)} icon={<BookOpen size={11} />} />
              <PM label="Cites" value={fmtCit(st.total_citations_covered)} icon={<TrendingUp size={11} />} />
              <PM label="Avg/Paper" value={fmtCit(st.avg_citations_per_read)} icon={<BarChart3 size={11} />} />
              <PM label="Pace" value={`${st.reading_pace_per_week}/wk`} icon={<TrendingUp size={11} />} />
              <PM label="Pubs" value={String(st.publication_count)} icon={<FileText size={11} />} />
            </div>
            <div className="flex gap-1 mt-4">
              {(['reading', 'publications', 'settings'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)} className={`flex-1 py-2 rounded-lg text-xs font-medium capitalize ${tab === t ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>{t}</button>))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {tab === 'reading' && (<div className="space-y-6">
              {profile.reading_by_microtopic && profile.reading_by_microtopic.length > 0 && (<div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Papers Read by Topic</p>
                  {readingByDomainAndTopic.domains.length > 1 && (
                    <div className="relative">
                      <select
                        value={selectedDomain}
                        onChange={(e) => setSelectedDomain(e.target.value)}
                        className="text-xs px-2 py-1 pr-6 rounded-lg border border-gray-200 bg-white text-gray-700 font-medium appearance-none cursor-pointer hover:border-gray-300 focus:outline-none focus:border-gray-400"
                      >
                        <option value="all">All Domains</option>
                        {readingByDomainAndTopic.domains.map(d => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                      <ChevronDown size={12} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    </div>
                  )}
                </div>
                <div className="space-y-4">
                  {Object.entries(readingByDomainAndTopic.byDomain)
                    .filter(([domain]) => selectedDomain === 'all' || selectedDomain === domain)
                    .map(([domain, topics]) => (
                      <div key={domain}>
                        {selectedDomain === 'all' && (
                          <p className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-2">{domain}</p>
                        )}
                        {Object.entries(topics).map(([topic, microtopics]) => {
                          const topicTotal = microtopics.reduce((sum, m) => sum + m.count, 0);
                          const topicPct = st.papers_read_count > 0 ? (topicTotal / st.papers_read_count) * 100 : 0;
                          const cat = getCatColor(topic);
                          return (
                            <div key={topic} className="mb-3">
                              <div className="flex items-center gap-2 mb-1.5">
                                <span className="text-[10px] font-semibold" style={{ color: cat.text }}>{topic.split('/').pop()}</span>
                                <div className="flex-1 h-1.5 bg-gray-100 rounded overflow-hidden">
                                  <div className="h-full rounded" style={{ width: `${topicPct}%`, backgroundColor: cat.border }} />
                                </div>
                                <span className="w-8 text-right text-[10px] text-gray-500 font-mono">{topicTotal}</span>
                              </div>
                              <div className="pl-3 space-y-1">
                                {microtopics.slice(0, 5).map((m) => {
                                  const microPct = topicTotal > 0 ? (m.count / topicTotal) * 100 : 0;
                                  return (
                                    <div key={m.microtopic_id} className="flex items-center gap-2">
                                      <span className="text-[9px] text-gray-500 flex-1 truncate">{m.microtopic_label}</span>
                                      <div className="w-20 h-1 bg-gray-50 rounded overflow-hidden">
                                        <div className="h-full rounded" style={{ width: `${microPct}%`, backgroundColor: cat.border + '80' }} />
                                      </div>
                                      <span className="w-6 text-right text-[9px] text-gray-400 font-mono">{m.count}</span>
                                    </div>
                                  );
                                })}
                                {microtopics.length > 5 && (
                                  <p className="text-[8px] text-gray-400 italic pl-2">+{microtopics.length - 5} more</p>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                </div>
              </div>)}
              {profile.reading_over_time.length > 0 && (<div>
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Reading Over Time</p>
                <div className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                  <div className="flex gap-2">
                    {/* Y-axis */}
                    <div className="flex flex-col justify-between h-24 py-0.5">
                      {(() => {
                        const max = Math.max(...profile.reading_over_time.map(m => m.count), 1);
                        const ticks = max <= 3 ? [max, Math.ceil(max / 2), 0] : [max, Math.ceil(max * 0.75), Math.ceil(max * 0.5), Math.ceil(max * 0.25), 0];
                        return ticks.map((tick, i) => (
                          <span key={i} className="text-[8px] text-gray-400 font-mono w-5 text-right">{tick}</span>
                        ));
                      })()}
                    </div>
                    {/* Bars */}
                    <div className="flex-1 flex items-end gap-1 h-24 border-l border-b border-gray-200">{profile.reading_over_time.map(({ month, count }, i) => {
                      const max = Math.max(...profile.reading_over_time.map(m => m.count), 1);
                      const containerHeight = 96; // h-24 = 96px
                      const heightPx = Math.max((count / max) * containerHeight, count > 0 ? 4 : 2);
                      return (<div key={month} className="flex-1 flex flex-col items-center justify-end" title={`${month}: ${count} papers`}>
                        <div className="w-full rounded-t" style={{ height: `${heightPx}px`, backgroundColor: i === profile.reading_over_time.length - 1 ? '#3b82f6' : '#94a3b8' }} />
                      </div>);
                    })}</div>
                  </div>
                  <div className="flex justify-between mt-1.5 ml-7 text-[8px] text-gray-400 font-mono">
                    <span>{profile.reading_over_time[0]?.month}</span><span>{profile.reading_over_time[profile.reading_over_time.length - 1]?.month}</span></div>
                </div></div>)}
              {profile.focus_topics.length > 0 && (<div><p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Focus Areas</p>
                <div className="flex flex-wrap gap-1.5">{profile.focus_topics.map(t => { const c = getCatColor(t); return <span key={t} className="px-2.5 py-1 rounded-full text-xs font-medium border" style={{ backgroundColor: c.fill, color: c.text, borderColor: c.border + '40' }}>{t}</span>; })}</div></div>)}
            </div>)}

            {tab === 'publications' && (<div className="space-y-6">
              <div className="grid grid-cols-3 gap-2">
                <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center"><p className="text-[8px] text-gray-400 uppercase">Published</p><p className="text-xl font-bold text-gray-800 font-mono">{pubs.length}</p></div>
                <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center"><p className="text-[8px] text-gray-400 uppercase">Total Cites</p><p className="text-xl font-bold text-gray-800 font-mono">{pubCites}</p></div>
                <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center"><p className="text-[8px] text-gray-400 uppercase">Days Active</p><p className="text-xl font-bold text-gray-800 font-mono">{st.days_since_join}</p></div>
              </div>
              <div><p className="text-[10px] font-semibold text-gray-400 uppercase mb-2">Linked Author</p>
                {profile.linked_author_id ? (
                  <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 border border-blue-200">
                    <div className="flex items-center gap-2"><User size={16} className="text-blue-500" /><div><p className="text-sm font-medium text-blue-800">{profile.linked_author_name}</p><p className="text-[10px] text-blue-500 font-mono">{profile.linked_author_id}</p></div></div>
                    <button onClick={unlinkAuthor} className="p-1.5 rounded-lg text-blue-400 hover:text-blue-600 hover:bg-blue-100"><Unlink size={14} /></button></div>
                ) : (<div className="space-y-2">
                  <p className="text-xs text-gray-500">Link your author profile to track publications.</p>
                  <div className="flex gap-2">
                    <input type="text" value={authorQ} onChange={e => setAuthorQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchAuthor()} placeholder="Search by name…" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none placeholder:text-gray-300" />
                    <button onClick={searchAuthor} disabled={searching} className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-medium disabled:opacity-50">{searching ? <Loader2 size={14} className="animate-spin" /> : 'Search'}</button>
                  </div>
                  {authorRes.length > 0 && <div className="space-y-1">{authorRes.map(a => (
                    <button key={a.author_id} onClick={() => linkAuthor(a.author_id)} disabled={linking} className="w-full flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-left disabled:opacity-50 disabled:cursor-not-allowed">
                      <User size={14} className="text-gray-400 shrink-0" /><div className="flex-1 min-w-0"><p className="text-sm font-medium text-gray-700">{a.name}</p>
                      <div className="flex gap-3 text-[10px] text-gray-400">{a.h_index != null && <span>h: {a.h_index}</span>}{a.works_count != null && <span>{a.works_count} papers</span>}</div></div>
                      {linking ? <Loader2 size={12} className="animate-spin text-blue-500 shrink-0" /> : <Link2 size={12} className="text-gray-300 shrink-0" />}</button>))}</div>}
                </div>)}
              </div>
              <div><p className="text-[10px] font-semibold text-gray-400 uppercase mb-2">Your Publications</p>
                {pubs.length > 0 ? <div className="space-y-2">{pubs.map(p => (
                  <div key={p.id} className="group p-3 rounded-xl border border-gray-200 hover:bg-gray-50"><div className="flex items-start justify-between gap-2"><div>
                    <p className="text-sm font-medium text-gray-700">{p.title}</p>
                    <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-400">{p.venue && <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium">{p.venue}</span>}<span>{p.year}</span><span>{p.citation_count} cites</span></div>
                  </div><button onClick={() => delPub(p.id)} className="p-1 rounded text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100"><X size={12} /></button></div></div>))}</div>
                  : <p className="text-xs text-gray-400 italic">No publications yet</p>}
              </div>
              <div><p className="text-[10px] font-semibold text-gray-400 uppercase mb-2">Add Publication</p>
                <div className="space-y-2">
                  <input type="text" value={pubTitle} onChange={e => setPubTitle(e.target.value)} placeholder="Title" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none placeholder:text-gray-300" />
                  <div className="flex gap-2"><input type="text" value={pubVenue} onChange={e => setPubVenue(e.target.value)} placeholder="Venue" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none placeholder:text-gray-300" />
                    <input type="number" value={pubYear} onChange={e => setPubYear(parseInt(e.target.value))} className="w-20 px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none" /></div>
                  <button onClick={addPub} disabled={!pubTitle.trim()} className="w-full py-2.5 rounded-lg bg-gray-800 text-white text-sm font-medium disabled:opacity-40 flex items-center justify-center gap-1.5"><Plus size={14} /> Add</button>
                </div></div>
            </div>)}

            {tab === 'settings' && (<div className="space-y-6">
              <div><p className="text-[10px] font-semibold text-gray-400 uppercase mb-2">Account</p>
                <div className="space-y-3">
                  <Row label="Username" value={profile.username} /><Row label="Email" value={profile.email} />
                  <Row label="Member Since" value={`${profile.created_at?.slice(0, 10)} (${st.days_since_join}d)`} />
                  <Row label="Linked Author" value={profile.linked_author_name || 'None'} />
                </div></div>
              <div><p className="text-[10px] font-semibold text-gray-400 uppercase mb-2">Data</p>
                <div className="p-3 rounded-xl border border-gray-200 space-y-2 text-xs">
                  <div className="flex justify-between"><span className="text-gray-500">Reading list</span><span className="font-mono text-gray-700">{st.reading_list_count}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Papers read</span><span className="font-mono text-gray-700">{st.papers_read_count}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Publications</span><span className="font-mono text-gray-700">{st.publication_count}</span></div>
                </div></div>
              <div><p className="text-[10px] font-semibold text-gray-400 uppercase mb-2">Actions</p>
                <div className="space-y-2">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <LogOut size={14} />
                    <span>Logout</span>
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-red-200 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={14} />
                    <span>Delete Account</span>
                  </button>
                </div></div>
            </div>)}
          </div>
        </div>
      </div>

      {/* Delete Account Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" onClick={(e) => e.stopPropagation()}>
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmText(''); }} />
          <div className="relative bg-white rounded-2xl shadow-2xl border border-gray-200 w-full max-w-md p-6 space-y-4 animate-fade-in-up">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                <Trash2 size={20} className="text-red-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-800">Delete Account</h3>
                <p className="text-sm text-gray-500 mt-1">
                  This action cannot be undone. This will permanently delete your account and remove all your data including:
                </p>
                <ul className="mt-2 space-y-1 text-xs text-gray-600">
                  <li>• Reading lists ({st.reading_list_count} papers)</li>
                  <li>• Read history ({st.papers_read_count} papers)</li>
                  <li>• Publications ({st.publication_count} items)</li>
                  <li>• All preferences and settings</li>
                </ul>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Type <span className="font-mono font-bold text-red-600">DELETE</span> to confirm:
              </label>
              <input
                type="text"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && deleteConfirmText === 'DELETE' && !deleting) {
                    handleDeleteAccount();
                  }
                }}
                placeholder="Type DELETE here"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                autoFocus
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmText(''); }}
                disabled={deleting}
                className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleteConfirmText !== 'DELETE' || deleting}
                className="flex-1 px-4 py-2.5 rounded-lg bg-red-600 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {deleting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Account</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PM({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (<div className="p-2 rounded-lg bg-gray-50 border border-gray-100 text-center">
    <div className="flex items-center justify-center gap-1 text-gray-400 mb-0.5">{icon}<span className="text-[7px] uppercase tracking-wider">{label}</span></div>
    <p className="text-sm font-bold text-gray-800 font-mono tabular-nums">{value}</p></div>);
}
function Row({ label, value }: { label: string; value: string }) {
  return (<div className="flex items-center justify-between p-3 rounded-xl border border-gray-200">
    <p className="text-sm font-medium text-gray-700">{label}</p><p className="text-xs text-gray-400">{value}</p></div>);
}

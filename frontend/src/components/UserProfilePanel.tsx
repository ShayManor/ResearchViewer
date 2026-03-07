import { useState } from 'react';
import { X, BookOpen, TrendingUp, User, Link2, Unlink, Plus, FileText, Award, BarChart3, Loader2 } from 'lucide-react';
import { getCategoryColor, formatCitations } from '../lib/colors';
import { getUserReadingStats, getSeedPaper, type UserProfileData, type Publication } from '../lib/dummy-data';
import { api } from '../lib/api';

interface Props {
  user: UserProfileData;
  onClose: () => void;
  onLinkAuthor: (id: string, name: string) => void;
  onUnlinkAuthor: () => void;
  onAddPublication: (pub: Publication) => void;
}

export function UserProfilePanel({ user, onClose, onLinkAuthor, onUnlinkAuthor, onAddPublication }: Props) {
  const [tab, setTab] = useState<'reading' | 'publications' | 'settings'>('reading');
  const [authorSearch, setAuthorSearch] = useState('');
  const [authorResults, setAuthorResults] = useState<{ author_id: string; name: string; h_index?: number; works_count?: number }[]>([]);
  const [searching, setSearching] = useState(false);
  const [pubTitle, setPubTitle] = useState('');
  const [pubVenue, setPubVenue] = useState('');
  const [pubYear, setPubYear] = useState(new Date().getFullYear());

  const stats = getUserReadingStats(user);
  const totalRead = user.readingList.length;
  const avgCitesPerPaper = totalRead > 0 ? Math.round(stats.totalCitationsRead / totalRead) : 0;
  const topCategory = stats.byTopic[0];

  // Days since join
  const daysSinceJoin = Math.floor((Date.now() - new Date(user.joinDate).getTime()) / (1000 * 60 * 60 * 24));
  const readingPace = daysSinceJoin > 0 ? (totalRead / (daysSinceJoin / 7)).toFixed(1) : '0';

  const searchAuthor = async () => {
    if (!authorSearch.trim()) return;
    setSearching(true);
    try {
      const res = await api.searchAuthors(authorSearch, 5);
      setAuthorResults(res.authors);
    } catch {
      setAuthorResults([]);
    }
    setSearching(false);
  };

  const addPub = () => {
    if (!pubTitle.trim()) return;
    onAddPublication({ doi: `shay/${Date.now()}`, title: pubTitle, venue: pubVenue || 'Unpublished', year: pubYear, citations: 0, coauthors: [] });
    setPubTitle(''); setPubVenue('');
  };

  // Publication stats
  const totalPubCitations = user.publications.reduce((s, p) => s + p.citations, 0);
  const pubsByYear = new Map<number, number>();
  for (const p of user.publications) pubsByYear.set(p.year, (pubsByYear.get(p.year) || 0) + 1);

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
          {/* Header */}
          <div className="px-6 py-5 border-b border-gray-100 shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gray-800 flex items-center justify-center text-xl font-bold text-white font-serif">{user.username[0]}</div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-800">{user.username}</h2>
                  <p className="text-xs text-gray-400">{user.email} · Joined {user.joinDate}</p>
                  {user.linkedAuthorName && (
                    <div className="flex items-center gap-1.5 mt-1">
                      <Link2 size={10} className="text-blue-500" />
                      <span className="text-[10px] text-blue-600 font-medium">Linked to {user.linkedAuthorName}</span>
                    </div>
                  )}
                </div>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"><X size={18} /></button>
            </div>

            {/* Summary metrics */}
            <div className="grid grid-cols-5 gap-2 mt-4">
              <ProfileMetric label="Papers Read" value={String(totalRead)} icon={<BookOpen size={12} />} />
              <ProfileMetric label="Cites Covered" value={formatCitations(stats.totalCitationsRead)} icon={<TrendingUp size={12} />} />
              <ProfileMetric label="Avg Cites/Paper" value={formatCitations(avgCitesPerPaper)} icon={<BarChart3 size={12} />} />
              <ProfileMetric label="Pace" value={`${readingPace}/wk`} icon={<TrendingUp size={12} />} />
              <ProfileMetric label="Publications" value={String(user.publications.length)} icon={<FileText size={12} />} />
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
                {/* Reading by topic */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Papers Read by Topic</p>
                  <div className="space-y-2">
                    {stats.byTopic.map(([topic, count]) => {
                      const cat = getCategoryColor(topic);
                      const pct = totalRead > 0 ? (count / totalRead) * 100 : 0;
                      return (
                        <div key={topic} className="flex items-center gap-2">
                          <span className="w-16 text-right text-[10px] font-medium shrink-0" style={{ color: cat.text }}>{topic}</span>
                          <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
                            <div className="h-full rounded transition-all" style={{ width: `${pct}%`, backgroundColor: cat.border }} />
                          </div>
                          <span className="w-10 text-right text-xs text-gray-600 font-mono font-medium">{count}</span>
                          <span className="w-10 text-right text-[10px] text-gray-400">{pct.toFixed(0)}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Reading over time */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Reading Activity Over Time</p>
                  {stats.byMonth.length > 0 ? (
                    <div className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                      <div className="flex items-end gap-1 h-20">
                        {stats.byMonth.map(([month, count], i) => {
                          const max = Math.max(...stats.byMonth.map(m => m[1] as number), 1);
                          const h = ((count as number) / max) * 100;
                          return (
                            <div key={month} className="flex-1 flex flex-col items-center gap-1" title={`${month}: ${count} papers`}>
                              <span className="text-[8px] text-gray-400 font-mono">{count}</span>
                              <div className="w-full rounded-t" style={{ height: `${h}%`, minHeight: 2, backgroundColor: i === stats.byMonth.length - 1 ? '#3b82f6' : '#94a3b8' }} />
                            </div>
                          );
                        })}
                      </div>
                      <div className="flex justify-between mt-1.5 text-[8px] text-gray-400 font-mono">
                        <span>{stats.byMonth[0][0]}</span>
                        <span>{stats.byMonth[stats.byMonth.length - 1][0]}</span>
                      </div>
                    </div>
                  ) : <p className="text-xs text-gray-400 italic">No reading history yet</p>}
                </div>

                {/* Focus areas */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Focus Areas</p>
                  <div className="flex flex-wrap gap-1.5">
                    {user.focusTopics.map(t => {
                      const cat = getCategoryColor(t);
                      return <span key={t} className="px-2.5 py-1 rounded-full text-xs font-medium border" style={{ backgroundColor: cat.fill, color: cat.text, borderColor: cat.border + '40' }}>{t}</span>;
                    })}
                  </div>
                </div>

                {/* Recent reads */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Recent Reads</p>
                  <div className="space-y-1.5">
                    {user.readHistory.slice(-5).reverse().map(entry => {
                      const paper = getSeedPaper(entry.doi);
                      if (!paper) return null;
                      return (
                        <div key={entry.doi} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 border border-gray-100">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-gray-700 font-medium truncate">{paper.title}</p>
                            <span className="text-[10px] text-gray-400">{formatCitations(paper.citation_count)} cites</span>
                          </div>
                          <span className="text-[10px] text-gray-400 font-mono shrink-0">{entry.readDate}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {tab === 'publications' && (
              <div className="space-y-6">
                {/* Publication stats */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center">
                    <p className="text-[8px] text-gray-400 uppercase tracking-wider">Published</p>
                    <p className="text-xl font-bold text-gray-800 font-mono">{user.publications.length}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center">
                    <p className="text-[8px] text-gray-400 uppercase tracking-wider">Total Cites</p>
                    <p className="text-xl font-bold text-gray-800 font-mono">{totalPubCitations}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-center">
                    <p className="text-[8px] text-gray-400 uppercase tracking-wider">Years Active</p>
                    <p className="text-xl font-bold text-gray-800 font-mono">{pubsByYear.size}</p>
                  </div>
                </div>

                {/* Linked author */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Linked Author Profile</p>
                  {user.linkedAuthorId ? (
                    <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 border border-blue-200">
                      <div className="flex items-center gap-2">
                        <User size={16} className="text-blue-500" />
                        <div>
                          <p className="text-sm font-medium text-blue-800">{user.linkedAuthorName}</p>
                          <p className="text-[10px] text-blue-500 font-mono">{user.linkedAuthorId}</p>
                        </div>
                      </div>
                      <button onClick={onUnlinkAuthor} className="p-1.5 rounded-lg text-blue-400 hover:text-blue-600 hover:bg-blue-100 transition-colors" title="Unlink"><Unlink size={14} /></button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-xs text-gray-500">Link your author profile to track publications and citations automatically.</p>
                      <div className="flex gap-2">
                        <input type="text" value={authorSearch} onChange={e => setAuthorSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchAuthor()}
                          placeholder="Search by name…" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-1 focus:ring-gray-300 placeholder:text-gray-300" />
                        <button onClick={searchAuthor} disabled={searching} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium disabled:opacity-50 transition-all">
                          {searching ? <Loader2 size={14} className="animate-spin" /> : 'Search'}
                        </button>
                      </div>
                      {authorResults.length > 0 && (
                        <div className="space-y-1">
                          {authorResults.map(a => (
                            <button key={a.author_id} onClick={() => { onLinkAuthor(a.author_id, a.name); setAuthorResults([]); setAuthorSearch(''); }}
                              className="w-full flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left">
                              <User size={14} className="text-gray-400 shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-700">{a.name}</p>
                                <div className="flex gap-3 text-[10px] text-gray-400">
                                  {a.h_index != null && <span>h-index: {a.h_index}</span>}
                                  {a.works_count != null && <span>{a.works_count} papers</span>}
                                </div>
                              </div>
                              <Link2 size={12} className="text-gray-300 shrink-0" />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Publication list */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Your Publications</p>
                  {user.publications.length > 0 ? (
                    <div className="space-y-2">
                      {user.publications.map(p => (
                        <div key={p.doi} className="p-3 rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors">
                          <p className="text-sm font-medium text-gray-700">{p.title}</p>
                          <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-400">
                            <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium">{p.venue}</span>
                            <span>{p.year}</span>
                            <span>{p.citations} citations</span>
                            {p.coauthors.length > 0 && <span>with {p.coauthors.join(', ')}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-xs text-gray-400 italic">No publications yet</p>}
                </div>

                {/* Add publication */}
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Add Publication</p>
                  <div className="space-y-2">
                    <input type="text" value={pubTitle} onChange={e => setPubTitle(e.target.value)} placeholder="Title" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-1 focus:ring-gray-300 placeholder:text-gray-300" />
                    <div className="flex gap-2">
                      <input type="text" value={pubVenue} onChange={e => setPubVenue(e.target.value)} placeholder="Venue / Conference" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-1 focus:ring-gray-300 placeholder:text-gray-300" />
                      <input type="number" value={pubYear} onChange={e => setPubYear(parseInt(e.target.value))} className="w-20 px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-gray-300" />
                    </div>
                    <button onClick={addPub} disabled={!pubTitle.trim()} className="w-full py-2.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium disabled:opacity-40 transition-all flex items-center justify-center gap-1.5">
                      <Plus size={14} /> Add Publication
                    </button>
                  </div>
                </div>
              </div>
            )}

            {tab === 'settings' && (
              <div className="space-y-6">
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Account</p>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-xl border border-gray-200">
                      <div>
                        <p className="text-sm font-medium text-gray-700">Username</p>
                        <p className="text-xs text-gray-400">{user.username}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl border border-gray-200">
                      <div>
                        <p className="text-sm font-medium text-gray-700">Email</p>
                        <p className="text-xs text-gray-400">{user.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl border border-gray-200">
                      <div>
                        <p className="text-sm font-medium text-gray-700">Member Since</p>
                        <p className="text-xs text-gray-400">{user.joinDate} ({daysSinceJoin} days)</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Focus Topics</p>
                  <div className="flex flex-wrap gap-1.5">
                    {user.focusTopics.map(t => {
                      const cat = getCategoryColor(t);
                      return <span key={t} className="px-2.5 py-1 rounded-full text-xs font-medium border" style={{ backgroundColor: cat.fill, color: cat.text, borderColor: cat.border + '40' }}>{t}</span>;
                    })}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Data</p>
                  <div className="p-3 rounded-xl border border-gray-200 space-y-2">
                    <div className="flex justify-between text-xs"><span className="text-gray-500">Reading list entries</span><span className="font-mono text-gray-700">{user.readingList.length}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-gray-500">Read history entries</span><span className="font-mono text-gray-700">{user.readHistory.length}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-gray-500">Publications</span><span className="font-mono text-gray-700">{user.publications.length}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-gray-500">Linked author</span><span className="font-mono text-gray-700">{user.linkedAuthorName || 'None'}</span></div>
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

function ProfileMetric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="p-2 rounded-lg bg-gray-50 border border-gray-100 text-center">
      <div className="flex items-center justify-center gap-1 text-gray-400 mb-0.5">{icon}<span className="text-[7px] uppercase tracking-wider">{label}</span></div>
      <p className="text-sm font-bold text-gray-800 font-mono tabular-nums">{value}</p>
    </div>
  );
}

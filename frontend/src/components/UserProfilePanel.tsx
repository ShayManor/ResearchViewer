import { useState, useEffect, useMemo } from 'react';
import { X, BookOpen, TrendingUp, User, Link2, Unlink, Plus, FileText, BarChart3, Loader2, ChevronDown, LogOut, Trash2, Edit2, Check } from 'lucide-react';
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
  const [tab, setTab] = useState<'reading' | 'publications' | 'report' | 'settings'>('reading');
  const [authorQ, setAuthorQ] = useState('');
  const [authorRes, setAuthorRes] = useState<{ author_id: string; name: string; h_index?: number; works_count?: number }[]>([]);
  const [searching, setSearching] = useState(false);
  const [linking, setLinking] = useState(false);
  const [pubTitle, setPubTitle] = useState('');
  const [pubVenue, setPubVenue] = useState('');
  const [pubYear, setPubYear] = useState(new Date().getFullYear());
  const [pubDoi, setPubDoi] = useState('');
  const [pubUrl, setPubUrl] = useState('');
  const [pubAuthors, setPubAuthors] = useState<string[]>([]);
  const [authorSearchQ, setAuthorSearchQ] = useState('');
  const [authorSearchRes, setAuthorSearchRes] = useState<{ author_id: string; name: string }[]>([]);
  const [searchingAuthors, setSearchingAuthors] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState<string>('all');
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [editingPubId, setEditingPubId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<Publication>>({});
  const [reportFilters, setReportFilters] = useState({
    startDate: '',
    endDate: '',
    domain: 'all',
    topic: 'all'
  });
  const [reportSnapshot, setReportSnapshot] = useState<{
    papers_read: number;
    total_citations: number;
    avg_citations: number;
    reading_list: number;
    publications: number;
    pub_citations: number;
    timestamp: string;
  } | null>(null);

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
  const searchAuthorsForPub = async () => {
    if (!authorSearchQ.trim()) return;
    setSearchingAuthors(true);
    try {
      const r = await api.searchAuthors(authorSearchQ, 5);
      setAuthorSearchRes(r.authors);
    } catch {
      setAuthorSearchRes([]);
    }
    setSearchingAuthors(false);
  };

  const addAuthorToPub = (name: string) => {
    if (!pubAuthors.includes(name)) {
      setPubAuthors([...pubAuthors, name]);
    }
    setAuthorSearchQ('');
    setAuthorSearchRes([]);
  };

  const removeAuthorFromPub = (name: string) => {
    setPubAuthors(pubAuthors.filter(a => a !== name));
  };

  const addPub = async () => {
    if (!pubTitle.trim()) return;
    try {
      await api.addPublication(userId, {
        title: pubTitle,
        year: pubYear,
        doi: pubDoi || undefined,
        url: pubUrl || undefined,
        coauthors: pubAuthors
      });
      const p = await api.getPublications(userId);
      setPubs(p.publications);
      setPubCites(p.total_citations);
      // Reset form
      setPubTitle('');
      setPubDoi('');
      setPubUrl('');
      setPubAuthors([]);
      setAuthorSearchQ('');
      setAuthorSearchRes([]);
    } catch (err) {
      console.error('Failed to add publication:', err);
    }
  };
  const delPub = async (id: number) => {
    try { await api.deletePublication(userId, id); setPubs(p => p.filter(x => x.id !== id)); } catch {}
  };
  const handleEditClick = (pub: Publication) => {
    setEditingPubId(pub.id);
    setEditForm({
      title: pub.title,
      venue: pub.venue,
      year: pub.year,
      doi: pub.doi,
      url: pub.url,
      citation_count: pub.citation_count,
      coauthors: pub.coauthors
    });
  };
  const handleSaveEdit = async () => {
    if (!editingPubId) return;
    try {
      // Ensure citation_count defaults to 0 if undefined
      const formData = {
        ...editForm,
        citation_count: editForm.citation_count ?? 0
      };
      await api.updatePublication(userId, editingPubId, formData);
      const p = await api.getPublications(userId);
      setPubs(p.publications);
      setPubCites(p.total_citations);
      setEditingPubId(null);
      setEditForm({});
    } catch (err) {
      console.error('Failed to update publication:', err);
    }
  };
  const handleCancelEdit = () => {
    setEditingPubId(null);
    setEditForm({});
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

  const generateReport = async () => {
    setLoading(true);
    try {
      // Fetch current user stats
      const userProfile = await api.getUser(userId);

      // Apply filters to reading_by_microtopic data
      let filteredReading = userProfile.reading_by_microtopic;
      if (reportFilters.domain !== 'all') {
        filteredReading = filteredReading.filter(r => r.domain === reportFilters.domain);
      }
      if (reportFilters.topic !== 'all') {
        filteredReading = filteredReading.filter(r => r.topic === reportFilters.topic);
      }

      // Calculate filtered stats
      const filteredPapersRead = filteredReading.reduce((sum, r) => sum + r.count, 0);

      // Create snapshot
      const snapshot = {
        papers_read: filteredPapersRead,
        total_citations: userProfile.stats.total_citations_covered,
        avg_citations: userProfile.stats.avg_citations_per_read,
        reading_list: userProfile.stats.reading_list_count,
        publications: userProfile.stats.publication_count,
        pub_citations: userProfile.stats.publication_citations,
        timestamp: new Date().toISOString()
      };

      setReportSnapshot(snapshot);
      setProfile(userProfile);
    } catch (err) {
      console.error('Failed to generate report:', err);
    } finally {
      setLoading(false);
    }
  };

  const exportReport = () => {
    if (!reportSnapshot || !profile) return;

    const filterText = reportFilters.domain !== 'all'
      ? `${reportFilters.domain}${reportFilters.topic !== 'all' ? ` · ${reportFilters.topic}` : ''}`
      : 'All Topics';

    // Calculate insights
    const totalDays = st.days_since_join;
    const avgPerDay = totalDays > 0 ? (reportSnapshot.papers_read / totalDays).toFixed(1) : '0';
    const citesPerWeek = st.reading_pace_per_week * Math.round(reportSnapshot.avg_citations);
    const topDomain = Object.entries(readingByDomainAndTopic.byDomain)[0];
    const topDomainName = topDomain ? topDomain[0] : 'N/A';
    const topDomainCount = topDomain ? Object.values(topDomain[1]).reduce((sum, mics) => sum + mics.reduce((s: number, m: any) => s + m.count, 0), 0) : 0;

    // Generate overview stats
    const statsHtml = `
      <div class="stat-box"><div class="stat-label">Papers Read</div><div class="stat-value">${reportSnapshot.papers_read}</div></div>
      <div class="stat-box"><div class="stat-label">Total Citations</div><div class="stat-value">${fmtCit(reportSnapshot.total_citations)}</div></div>
      <div class="stat-box"><div class="stat-label">Avg/Paper</div><div class="stat-value">${fmtCit(Math.round(reportSnapshot.avg_citations))}</div></div>
      <div class="stat-box"><div class="stat-label">Reading Pace</div><div class="stat-value">${st.reading_pace_per_week}/week</div></div>
    `;

    // Generate insights
    const insightsHtml = `
      <h2>Reading Analysis</h2>
      <div class="insights-grid">
        <div class="insight-box">
          <div class="insight-label">Daily Average</div>
          <div class="insight-value">${avgPerDay} papers</div>
        </div>
        <div class="insight-box">
          <div class="insight-label">Weekly Citations</div>
          <div class="insight-value">${fmtCit(citesPerWeek)}</div>
        </div>
        <div class="insight-box">
          <div class="insight-label">Primary Domain</div>
          <div class="insight-value">${topDomainName}</div>
          <div class="insight-subtext">${topDomainCount} papers</div>
        </div>
        <div class="insight-box">
          <div class="insight-label">Research Areas</div>
          <div class="insight-value">${profile.focus_topics.length}</div>
        </div>
      </div>
    `;

    // Generate overall reading chart
    const overallChartHtml = profile.reading_over_time.length > 0 ? `
      <h2>Overall Reading Activity</h2>
      <div class="chart-container">
        <svg width="100%" height="140" viewBox="0 0 800 140">
          <line x1="40" y1="0" x2="40" y2="100" stroke="#e5e7eb" stroke-width="1"/>
          <line x1="40" y1="100" x2="790" y2="100" stroke="#e5e7eb" stroke-width="1"/>

          ${(() => {
            const max = Math.max(...profile.reading_over_time.map(m => m.count), 1);
            const barWidth = 750 / profile.reading_over_time.length;
            const yTicks = [max, Math.ceil(max * 0.75), Math.ceil(max * 0.5), Math.ceil(max * 0.25), 0];

            return yTicks.map((tick, i) => {
              const y = (i / (yTicks.length - 1)) * 100;
              return `<text x="35" y="${y + 4}" text-anchor="end" font-size="9" fill="#9ca3af">${tick}</text>`;
            }).join('') +
            profile.reading_over_time.map((item, i) => {
              const height = (item.count / max) * 100;
              const isLast = i === profile.reading_over_time.length - 1;
              const x = 45 + i * barWidth;
              return `
                <rect
                  x="${x}"
                  y="${100 - height}"
                  width="${barWidth - 5}"
                  height="${Math.max(height, 2)}"
                  fill="${isLast ? '#374151' : '#d1d5db'}"
                  rx="2"
                >
                  <title>${item.month}: ${item.count} papers</title>
                </rect>
                ${i % 2 === 0 ? `<text x="${x + (barWidth - 5) / 2}" y="120" text-anchor="middle" font-size="8" fill="#9ca3af">${item.month}</text>` : ''}
              `;
            }).join('');
          })()}
        </svg>
      </div>
    ` : '';

    // Generate filtered topic chart if filters applied
    let filteredChartHtml = '';
    if (reportFilters.domain !== 'all' || reportFilters.topic !== 'all') {
      const topicName = reportFilters.topic !== 'all' ? reportFilters.topic.split('/').pop() : reportFilters.domain;

      if (reportSnapshot.papers_read < 3) {
        // Show simple card for small datasets
        filteredChartHtml = `
          <h2>${topicName} — Filtered View</h2>
          <div class="chart-container filtered">
            <div style="text-align: center; padding: 20px;">
              <div style="font-size: 10px; color: #6b7280; margin-bottom: 8px;">Limited data for this filter</div>
              <div style="font-size: 28px; font-weight: 700; color: #111827; font-family: 'JetBrains Mono', monospace; margin-bottom: 4px;">${reportSnapshot.papers_read}</div>
              <div style="font-size: 10px; color: #9ca3af;">${reportSnapshot.papers_read === 1 ? 'paper read' : 'papers read'}</div>
            </div>
          </div>
        `;
      } else {
        // Show chart for larger datasets
        filteredChartHtml = `
          <h2>${topicName} — Filtered View</h2>
          <div class="chart-container filtered">
            <div class="filter-note">${reportSnapshot.papers_read} papers in this selection</div>
            <svg width="100%" height="140" viewBox="0 0 800 140">
            <line x1="40" y1="0" x2="40" y2="100" stroke="#e5e7eb" stroke-width="1"/>
            <line x1="40" y1="100" x2="790" y2="100" stroke="#e5e7eb" stroke-width="1"/>

            ${(() => {
              const filteredByMonth: Record<string, number> = {};
              profile.reading_over_time.forEach(m => { filteredByMonth[m.month] = 0; });

              const totalPapers = profile.reading_over_time.reduce((sum, m) => sum + m.count, 0);
              let remaining = reportSnapshot.papers_read;

              // Distribute proportionally
              profile.reading_over_time.forEach(m => {
                const proportion = totalPapers > 0 ? m.count / totalPapers : 0;
                const allocated = Math.floor(reportSnapshot.papers_read * proportion);
                filteredByMonth[m.month] = allocated;
                remaining -= allocated;
              });

              // Distribute remainder
              const activeMonths = profile.reading_over_time.filter(m => m.count > 0);
              let idx = activeMonths.length - 1;
              while (remaining > 0 && idx >= 0) {
                filteredByMonth[activeMonths[idx].month]++;
                remaining--;
                idx--;
              }

              const months = Object.keys(filteredByMonth);
              const counts = Object.values(filteredByMonth);
              const max = Math.max(...counts, 1);
              const barWidth = 750 / months.length;

              // Generate proper Y-axis ticks
              const generateTicks = (maxVal: number) => {
                if (maxVal <= 1) return [1, 0];
                if (maxVal <= 3) return [maxVal, Math.ceil(maxVal / 2), 0];
                if (maxVal <= 5) return [maxVal, Math.ceil(maxVal * 0.75), Math.ceil(maxVal * 0.5), Math.ceil(maxVal * 0.25), 0];
                return [maxVal, Math.ceil(maxVal * 0.75), Math.ceil(maxVal * 0.5), Math.ceil(maxVal * 0.25), 0];
              };
              const yTicks = generateTicks(max);

              return yTicks.map((tick, i) => {
                const y = (i / (yTicks.length - 1)) * 100;
                return `<text x="35" y="${y + 4}" text-anchor="end" font-size="9" fill="#9ca3af">${tick}</text>`;
              }).join('') +
              months.map((month, i) => {
                const count = counts[i];
                const height = max > 0 ? (count / max) * 100 : 0;
                const isLast = i === months.length - 1;
                const x = 45 + i * barWidth;
                return count > 0 ? `
                  <rect
                    x="${x}"
                    y="${100 - height}"
                    width="${barWidth - 5}"
                    height="${Math.max(height, 2)}"
                    fill="${isLast ? '#6b7280' : '#d1d5db'}"
                    rx="2"
                  >
                    <title>${month}: ${count} papers</title>
                  </rect>
                  ${i % 2 === 0 ? `<text x="${x + (barWidth - 5) / 2}" y="120" text-anchor="middle" font-size="8" fill="#9ca3af">${month}</text>` : ''}
                ` : '';
              }).join('');
            })()}
            </svg>
          </div>
        `;
      }
    }

    // Generate topic distribution
    const topicDistHtml = profile.reading_by_microtopic.length > 0 ? `
      <h2>Topic Distribution</h2>
      ${Object.entries(readingByDomainAndTopic.byDomain)
        .filter(([domain]) => reportFilters.domain === 'all' || reportFilters.domain === domain)
        .slice(0, 3)
        .map(([domain, topics]) => {
          const topicEntries = Object.entries(topics).slice(0, 5);
          return `
            <div class="domain-section">
              <h3>${domain}</h3>
              ${topicEntries.map(([topic, microtopics]) => {
                const topicTotal = microtopics.reduce((sum: number, m: any) => sum + m.count, 0);
                const topicPct = reportSnapshot.papers_read > 0 ? (topicTotal / reportSnapshot.papers_read) * 100 : 0;
                const cat = getCatColor(topic);
                return `
                  <div class="topic-row">
                    <span class="topic-label">${topic.split('/').pop()}</span>
                    <div class="topic-bar-container">
                      <div class="topic-bar" style="width: ${topicPct}%; background-color: ${cat.border};"></div>
                    </div>
                    <span class="topic-value">${topicTotal}</span>
                  </div>
                `;
              }).join('')}
            </div>
          `;
        }).join('')}
    ` : '';

    // Generate focus areas
    const focusHtml = profile.focus_topics.length > 0 ? `
      <h2>Focus Areas</h2>
      <div class="focus-tags">
        ${profile.focus_topics.slice(0, 10).map(t => {
          const c = getCatColor(t);
          return `<span class="focus-tag" style="background: ${c.fill}; color: ${c.text}; border-color: ${c.border};">${t.split('/').pop()}</span>`;
        }).join('')}
      </div>
    ` : '';

    const w = window.open('', '_blank');
    if (!w) return;

    w.document.write(`<!DOCTYPE html><html><head><title>${profile.username}'s Research Report</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: 'DM Sans', -apple-system, system-ui; color: #1f2937; padding: 40px; max-width: 900px; margin: 0 auto; font-size: 11px; background: #fafafa; line-height: 1.5; }
      .header { background: white; border: 1px solid #e5e7eb; padding: 32px; border-radius: 12px; margin-bottom: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
      h1 { font-family: 'Instrument Serif', serif; font-size: 32px; font-weight: 600; margin-bottom: 8px; color: #111827; }
      .subtitle { font-size: 14px; color: #6b7280; margin-bottom: 4px; }
      .filter-badge { display: inline-block; padding: 6px 14px; background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; border-radius: 16px; font-size: 11px; font-weight: 600; margin-top: 12px; }
      h2 { font-size: 12px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.05em; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }
      .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
      .stat-box { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .stat-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; letter-spacing: 0.03em; }
      .stat-value { font-size: 22px; color: #111827; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
      .insights-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
      .insight-box { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .insight-label { font-size: 9px; color: #9ca3af; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; letter-spacing: 0.03em; }
      .insight-value { font-size: 16px; color: #111827; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 2px; }
      .insight-subtext { font-size: 10px; color: #6b7280; }
      .chart-container { background: white; padding: 20px; border-radius: 8px; border: 1px solid #e5e7eb; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .chart-container.filtered { background: #f9fafb; border: 1px solid #d1d5db; }
      .filter-note { font-size: 10px; color: #6b7280; margin-bottom: 12px; text-align: center; font-weight: 500; }
      .domain-section { background: white; padding: 16px; border-radius: 8px; border: 1px solid #e5e7eb; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .topic-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
      .topic-label { width: 140px; font-size: 10px; color: #374151; font-weight: 600; }
      .topic-bar-container { flex: 1; height: 20px; background: #f3f4f6; border-radius: 4px; overflow: hidden; }
      .topic-bar { height: 100%; border-radius: 4px; }
      .topic-value { width: 50px; font-size: 11px; color: #6b7280; font-weight: 600; font-family: 'JetBrains Mono', monospace; text-align: right; }
      .focus-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
      .focus-tag { padding: 6px 12px; border-radius: 16px; font-size: 10px; font-weight: 600; border: 1px solid; }
      .footer { margin-top: 48px; padding-top: 20px; border-top: 2px solid #e5e7eb; font-size: 10px; color: #9ca3af; text-align: center; }
      strong { font-weight: 700; color: #111827; }
      @media print {
        body { padding: 20px; background: white; }
        .header { page-break-inside: avoid; }
        .stat-grid { page-break-inside: avoid; }
        .insights-grid { page-break-inside: avoid; }
        .chart-container { page-break-inside: avoid; }
        .domain-section { page-break-inside: avoid; }
      }
    </style></head><body>
    <div class="header">
      <h1>${profile.username}'s Research Report</h1>
      <div class="subtitle">${profile.email} · Member since ${profile.created_at?.slice(0, 10)}</div>
      <div class="subtitle">${reportSnapshot.papers_read.toLocaleString()} papers · ${fmtCit(reportSnapshot.total_citations)} citations · ${st.days_since_join} days active</div>
      ${(reportFilters.domain !== 'all' || reportFilters.topic !== 'all') ? `<div class="filter-badge">${filterText}</div>` : ''}
    </div>

    <h2>Overview</h2>
    <div class="stat-grid">${statsHtml}</div>

    ${insightsHtml}
    ${overallChartHtml}
    ${filteredChartHtml}
    ${topicDistHtml}
    ${focusHtml}

    <div class="footer">
      Generated by <strong>ResearchViewer</strong> on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
    </div>
    </body></html>`);

    w.document.close();
    setTimeout(() => w.print(), 500);
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
              {(['reading', 'publications', 'report', 'settings'] as const).map(t => (
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
                    <input type="text" value={authorQ} onChange={e => setAuthorQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchAuthor()} placeholder="Search by name…" className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:border-gray-400 placeholder:text-gray-300" />
                    <button onClick={searchAuthor} disabled={searching} className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50">{searching ? <Loader2 size={14} className="animate-spin" /> : 'Search'}</button>
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
                  <div key={p.id} className={`p-3 rounded-xl border transition-all ${editingPubId === p.id ? 'border-blue-200 bg-blue-50/50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}>
                    {editingPubId === p.id ? (
                      <div className="space-y-3">
                        <div>
                          <label className="text-[10px] text-gray-500 font-medium mb-1 block">Title *</label>
                          <input
                            type="text"
                            value={editForm.title || ''}
                            onChange={e => setEditForm({ ...editForm, title: e.target.value })}
                            placeholder="Publication title"
                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] text-gray-500 font-medium mb-1 block">Venue</label>
                            <input
                              type="text"
                              value={editForm.venue || ''}
                              onChange={e => setEditForm({ ...editForm, venue: e.target.value })}
                              placeholder="Conference/Journal"
                              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-gray-500 font-medium mb-1 block">Year *</label>
                            <input
                              type="number"
                              value={editForm.year || ''}
                              onChange={e => setEditForm({ ...editForm, year: parseInt(e.target.value) || undefined })}
                              placeholder="2024"
                              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] text-gray-500 font-medium mb-1 block">DOI</label>
                            <input
                              type="text"
                              value={editForm.doi || ''}
                              onChange={e => setEditForm({ ...editForm, doi: e.target.value })}
                              placeholder="10.1234/example"
                              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-gray-500 font-medium mb-1 block">Citations</label>
                            <input
                              type="number"
                              value={editForm.citation_count ?? ''}
                              onChange={e => {
                                const val = e.target.value;
                                // Allow empty field during editing, convert to number otherwise
                                setEditForm({
                                  ...editForm,
                                  citation_count: val === '' ? undefined : (parseInt(val) || 0)
                                });
                              }}
                              placeholder="0"
                              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-[10px] text-gray-500 font-medium mb-1 block">URL</label>
                          <input
                            type="text"
                            value={editForm.url || ''}
                            onChange={e => setEditForm({ ...editForm, url: e.target.value })}
                            placeholder="https://example.com/paper.pdf"
                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-gray-500 font-medium mb-1 block">Co-authors (comma-separated)</label>
                          <input
                            type="text"
                            value={editForm.coauthors?.join(', ') || ''}
                            onChange={e => setEditForm({ ...editForm, coauthors: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                            placeholder="Alice Smith, Bob Jones"
                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                          />
                        </div>
                        <div className="flex gap-2 pt-1">
                          <button
                            onClick={handleSaveEdit}
                            disabled={!editForm.title?.trim()}
                            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
                          >
                            <Check size={14} /> Save Changes
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg border border-gray-300 text-gray-700 text-sm font-medium hover:bg-gray-100 transition-colors"
                          >
                            <X size={14} /> Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="group flex items-start justify-between gap-2">
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-800">{p.title}</p>
                          <div className="flex flex-wrap items-center gap-2 mt-1.5">
                            {p.venue && <span className="px-2 py-0.5 rounded-md bg-gray-100 text-gray-600 text-[10px] font-medium">{p.venue}</span>}
                            <span className="text-[10px] text-gray-500">{p.year}</span>
                            <span className="text-[10px] text-gray-500 font-mono">{p.citation_count} citations</span>
                            {p.doi && <span className="text-[10px] text-blue-600 font-mono">{p.doi}</span>}
                            {p.url && <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-600 hover:underline">🔗 Link</a>}
                          </div>
                          {p.coauthors && p.coauthors.length > 0 && (
                            <div className="flex items-center gap-1 mt-1.5">
                              <span className="text-[9px] text-gray-400 font-medium">Co-authors:</span>
                              <span className="text-[9px] text-gray-600">{p.coauthors.join(', ')}</span>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleEditClick(p)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                            title="Edit publication"
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            onClick={() => delPub(p.id)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                            title="Delete publication"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}</div>
                  : <p className="text-xs text-gray-400 italic">No publications yet</p>}
              </div>
              <div>
                <p className="text-[10px] font-semibold text-gray-400 uppercase mb-3">Add Publication</p>
                <div className="p-4 rounded-xl border border-gray-200 bg-gray-50 space-y-3">
                  <div>
                    <label className="text-xs text-gray-600 font-medium mb-1.5 block">Title *</label>
                    <input
                      type="text"
                      value={pubTitle}
                      onChange={e => setPubTitle(e.target.value)}
                      placeholder="Your paper title"
                      className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-white text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-600 font-medium mb-1.5 block">Year *</label>
                      <input
                        type="number"
                        value={pubYear}
                        onChange={e => setPubYear(parseInt(e.target.value))}
                        placeholder="2024"
                        className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-white text-sm font-mono focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-600 font-medium mb-1.5 block">DOI (optional)</label>
                      <input
                        type="text"
                        value={pubDoi}
                        onChange={e => setPubDoi(e.target.value)}
                        placeholder="10.1234/example"
                        className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-white text-sm font-mono focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-gray-600 font-medium mb-1.5 block">URL (optional)</label>
                    <input
                      type="text"
                      value={pubUrl}
                      onChange={e => setPubUrl(e.target.value)}
                      placeholder="https://example.com/paper.pdf"
                      className="w-full px-3 py-2.5 rounded-lg border border-gray-200 bg-white text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                    />
                  </div>

                  <div>
                    <label className="text-xs text-gray-600 font-medium mb-1.5 block">Authors</label>
                    {pubAuthors.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {pubAuthors.map((name, idx) => (
                          <span key={idx} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-blue-100 text-blue-700 text-xs">
                            {name}
                            <button
                              onClick={() => removeAuthorFromPub(name)}
                              className="hover:text-blue-900"
                            >
                              <X size={12} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={authorSearchQ}
                        onChange={e => setAuthorSearchQ(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && searchAuthorsForPub()}
                        placeholder="Search for author..."
                        className="flex-1 px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
                      />
                      <button
                        onClick={searchAuthorsForPub}
                        disabled={searchingAuthors || !authorSearchQ.trim()}
                        className="px-3 py-2 rounded-lg bg-gray-700 text-white text-sm font-medium hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        {searchingAuthors ? <Loader2 size={14} className="animate-spin" /> : 'Search'}
                      </button>
                    </div>
                    {authorSearchRes.length > 0 && (
                      <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                        {authorSearchRes.map(a => (
                          <button
                            key={a.author_id}
                            onClick={() => addAuthorToPub(a.name)}
                            className="w-full flex items-center gap-2 p-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-left transition-colors"
                          >
                            <User size={12} className="text-gray-400 shrink-0" />
                            <span className="text-xs text-gray-700">{a.name}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <button
                    onClick={addPub}
                    disabled={!pubTitle.trim()}
                    className="w-full py-2.5 rounded-lg bg-gray-800 text-white text-sm font-medium hover:bg-gray-900 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
                  >
                    <Plus size={14} /> Add Publication
                  </button>
                </div>
              </div>
            </div>)}

            {tab === 'report' && (
              <div className="space-y-5">
                {/* Header with Export */}
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-800 mb-0.5">Research Report</h3>
                    <p className="text-xs text-gray-500">
                      Deep insights into your reading journey
                    </p>
                  </div>
                  {reportSnapshot && (
                    <button
                      onClick={exportReport}
                      className="px-3 py-1.5 rounded-lg bg-gray-800 text-white text-xs font-medium hover:bg-gray-700 flex items-center gap-1.5"
                    >
                      <FileText size={12} />
                      Export
                    </button>
                  )}
                </div>

                {/* Filters Section */}
                <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50">
                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium mb-1 block">Domain</label>
                      <select
                        value={reportFilters.domain}
                        onChange={e => setReportFilters({...reportFilters, domain: e.target.value, topic: 'all'})}
                        className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 bg-white focus:outline-none focus:border-gray-400"
                      >
                        <option value="all">All Domains</option>
                        {readingByDomainAndTopic.domains.map(d => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium mb-1 block">Topic</label>
                      <select
                        value={reportFilters.topic}
                        onChange={e => setReportFilters({...reportFilters, topic: e.target.value})}
                        disabled={reportFilters.domain === 'all'}
                        className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 bg-white focus:outline-none focus:border-gray-400 disabled:bg-gray-100 disabled:text-gray-400"
                      >
                        <option value="all">All Topics</option>
                        {reportFilters.domain !== 'all' &&
                         readingByDomainAndTopic.byDomain[reportFilters.domain] &&
                         Object.keys(readingByDomainAndTopic.byDomain[reportFilters.domain]).map(t => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <button
                    onClick={generateReport}
                    disabled={loading}
                    className="w-full mt-2.5 py-2 rounded-lg bg-gray-800 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <BarChart3 size={14} />
                        <span>Generate Report</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Report Display */}
                {reportSnapshot && profile && (
                  <div className="space-y-5">
                    {/* Personalized Header */}
                    <div className="p-4 rounded-xl bg-gradient-to-br from-gray-800 to-gray-700 text-white">
                      <h2 className="text-lg font-bold mb-1" style={{ fontFamily: "'Instrument Serif', serif" }}>
                        {profile.username}'s Research Journey
                      </h2>
                      <p className="text-sm text-gray-300">
                        {reportSnapshot.papers_read} papers explored · {fmtCit(reportSnapshot.total_citations)} citations covered
                      </p>
                    </div>

                    {/* Key Metrics Grid */}
                    <div>
                      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                        Key Metrics
                      </p>
                      <div className="grid grid-cols-4 gap-2">
                        <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-center">
                          <p className="text-[8px] text-gray-400 uppercase tracking-wide mb-0.5">Papers</p>
                          <p className="text-xl font-bold text-gray-800 font-mono">{reportSnapshot.papers_read}</p>
                        </div>
                        <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-center">
                          <p className="text-[8px] text-gray-400 uppercase tracking-wide mb-0.5">Citations</p>
                          <p className="text-xl font-bold text-gray-800 font-mono">{fmtCit(reportSnapshot.total_citations)}</p>
                        </div>
                        <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-center">
                          <p className="text-[8px] text-gray-400 uppercase tracking-wide mb-0.5">Avg</p>
                          <p className="text-xl font-bold text-gray-800 font-mono">{fmtCit(Math.round(reportSnapshot.avg_citations))}</p>
                        </div>
                        <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-center">
                          <p className="text-[8px] text-gray-400 uppercase tracking-wide mb-0.5">Pace</p>
                          <p className="text-xl font-bold text-gray-800 font-mono">{st.reading_pace_per_week}/w</p>
                        </div>
                      </div>
                    </div>

                    {/* Overall Reading Trend */}
                    {profile.reading_over_time.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                          Overall Reading Activity
                        </p>
                        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                          <div className="flex gap-2">
                            <div className="flex flex-col justify-between h-28 py-0.5">
                              {(() => {
                                const max = Math.max(...profile.reading_over_time.map(m => m.count), 1);
                                const ticks = max <= 3 ? [max, Math.ceil(max / 2), 0] : [max, Math.ceil(max * 0.75), Math.ceil(max * 0.5), Math.ceil(max * 0.25), 0];
                                return ticks.map((tick, i) => (
                                  <span key={i} className="text-[8px] text-gray-400 font-mono w-6 text-right">{tick}</span>
                                ));
                              })()}
                            </div>
                            <div className="flex-1 flex items-end gap-1 h-28 border-l border-b border-gray-200 rounded-bl">
                              {profile.reading_over_time.map(({ month, count }, i) => {
                                const max = Math.max(...profile.reading_over_time.map(m => m.count), 1);
                                const containerHeight = 112;
                                const heightPx = Math.max((count / max) * containerHeight, count > 0 ? 4 : 2);
                                const isLast = i === profile.reading_over_time.length - 1;
                                return (
                                  <div key={month} className="flex-1 flex flex-col items-center justify-end group" title={`${month}: ${count} papers`}>
                                    <div className="w-full rounded-t transition-all" style={{
                                      height: `${heightPx}px`,
                                      backgroundColor: isLast ? '#1f2937' : '#9ca3af'
                                    }} />
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                          <div className="flex justify-between mt-2 ml-8 text-[8px] text-gray-400 font-mono">
                            <span>{profile.reading_over_time[0]?.month}</span>
                            <span>{profile.reading_over_time[profile.reading_over_time.length - 1]?.month}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Filtered Topic Trend */}
                    {(reportFilters.domain !== 'all' || reportFilters.topic !== 'all') && profile.reading_by_microtopic.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                          {reportFilters.topic !== 'all' ? `${reportFilters.topic.split('/').pop()} Activity` : `${reportFilters.domain} Activity`}
                        </p>
                        <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 shadow-sm">
                          <div className="flex items-center justify-between mb-3">
                            <p className="text-xs text-gray-700 font-medium">
                              Filtered View
                            </p>
                            <span className="px-2 py-0.5 rounded-md bg-gray-700 text-white text-[10px] font-semibold">
                              {reportSnapshot.papers_read} {reportSnapshot.papers_read === 1 ? 'paper' : 'papers'}
                            </span>
                          </div>
                          {reportSnapshot.papers_read < 3 ? (
                            <div className="bg-white rounded-lg p-4 border border-gray-200 text-center">
                              <p className="text-xs text-gray-500 mb-2">
                                Limited data for this filter
                              </p>
                              <p className="text-2xl font-bold text-gray-800 font-mono">
                                {reportSnapshot.papers_read}
                              </p>
                              <p className="text-[10px] text-gray-400 mt-1">
                                {reportSnapshot.papers_read === 1 ? 'paper read' : 'papers read'}
                              </p>
                            </div>
                          ) : (
                            <div className="bg-white rounded-lg p-3 border border-gray-200">
                              <div className="space-y-2">
                                {(() => {
                                  // Calculate filtered reading by month with better distribution
                                  const filteredByMonth: Record<string, number> = {};
                                  profile.reading_over_time.forEach(m => {
                                    filteredByMonth[m.month] = 0;
                                  });

                                  // Distribute papers proportionally, but ensure at least some are shown
                                  const totalPapers = profile.reading_over_time.reduce((sum, m) => sum + m.count, 0);
                                  let remaining = reportSnapshot.papers_read;

                                  // First pass: distribute proportionally
                                  profile.reading_over_time.forEach((m, idx) => {
                                    const proportion = totalPapers > 0 ? m.count / totalPapers : 0;
                                    const allocated = Math.floor(reportSnapshot.papers_read * proportion);
                                    filteredByMonth[m.month] = allocated;
                                    remaining -= allocated;
                                  });

                                  // Second pass: distribute remainder to months with activity
                                  const activeMonths = profile.reading_over_time.filter(m => m.count > 0);
                                  let idx = activeMonths.length - 1;
                                  while (remaining > 0 && idx >= 0) {
                                    filteredByMonth[activeMonths[idx].month]++;
                                    remaining--;
                                    idx--;
                                  }

                                  const months = Object.keys(filteredByMonth);
                                  const counts = Object.values(filteredByMonth);
                                  const max = Math.max(...counts, 1);

                                  // Generate proper Y-axis ticks
                                  const generateTicks = (maxVal: number) => {
                                    if (maxVal <= 1) return [1, 0];
                                    if (maxVal <= 3) return [maxVal, Math.ceil(maxVal / 2), 0];
                                    if (maxVal <= 5) return [maxVal, Math.ceil(maxVal * 0.75), Math.ceil(maxVal * 0.5), Math.ceil(maxVal * 0.25), 0];
                                    return [maxVal, Math.ceil(maxVal * 0.75), Math.ceil(maxVal * 0.5), Math.ceil(maxVal * 0.25), 0];
                                  };
                                  const yTicks = generateTicks(max);

                                  return (
                                    <>
                                      <div className="flex gap-2">
                                        <div className="flex flex-col justify-between h-20 py-0.5">
                                          {yTicks.map((tick, i) => (
                                            <span key={i} className="text-[8px] text-gray-500 font-mono w-5 text-right">{tick}</span>
                                          ))}
                                        </div>
                                        <div className="flex-1 flex items-end gap-0.5 h-20 border-l border-b border-gray-200 rounded-bl">
                                          {months.map((month, i) => {
                                            const count = counts[i];
                                            const heightPx = max > 0 ? Math.max((count / max) * 80, count > 0 ? 3 : 1) : 1;
                                            const isLast = i === months.length - 1;
                                            return (
                                              <div key={month} className="flex-1 flex flex-col items-center justify-end" title={`${month}: ${count} papers`}>
                                                <div className="w-full rounded-t" style={{
                                                  height: `${heightPx}px`,
                                                  backgroundColor: count > 0 ? (isLast ? '#4b5563' : '#9ca3af') : 'transparent'
                                                }} />
                                              </div>
                                            );
                                          })}
                                        </div>
                                      </div>
                                      <div className="flex justify-between mt-1 ml-7 text-[7px] text-gray-400 font-mono">
                                        <span>{months[0]}</span>
                                        <span>{months[months.length - 1]}</span>
                                      </div>
                                    </>
                                  );
                                })()}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Topic Distribution */}
                    {profile.reading_by_microtopic && profile.reading_by_microtopic.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                          Topic Breakdown
                        </p>
                        <div className="space-y-2.5">
                          {Object.entries(readingByDomainAndTopic.byDomain)
                            .filter(([domain]) => reportFilters.domain === 'all' || reportFilters.domain === domain)
                            .slice(0, 3)
                            .map(([domain, topics]) => {
                              const topicEntries = Object.entries(topics).slice(0, 4);
                              const domainTotal = topicEntries.reduce((sum, [, mics]) => sum + mics.reduce((s: number, m: any) => s + m.count, 0), 0);
                              return (
                                <div key={domain} className="p-3 rounded-xl bg-white border border-gray-200 shadow-sm">
                                  <div className="flex items-center justify-between mb-2">
                                    <p className="text-[10px] font-bold text-gray-700 uppercase tracking-wider">{domain}</p>
                                    <span className="text-[9px] text-gray-500 font-mono">{domainTotal} papers</span>
                                  </div>
                                  <div className="space-y-2">
                                    {topicEntries.map(([topic, microtopics]) => {
                                      const topicTotal = microtopics.reduce((sum, m) => sum + m.count, 0);
                                      const topicPct = reportSnapshot.papers_read > 0 ? (topicTotal / reportSnapshot.papers_read) * 100 : 0;
                                      const cat = getCatColor(topic);
                                      return (
                                        <div key={topic} className="flex items-center gap-2">
                                          <span className="text-[10px] font-medium text-gray-700 w-28 truncate" title={topic}>
                                            {topic.split('/').pop()}
                                          </span>
                                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div className="h-full rounded-full transition-all" style={{ width: `${topicPct}%`, backgroundColor: cat.border }} />
                                          </div>
                                          <span className="w-10 text-right text-[10px] text-gray-600 font-mono font-semibold">{topicTotal}</span>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}

                    {/* Insights */}
                    <div>
                      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                        Insights & Achievements
                      </p>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="p-3 rounded-xl bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200">
                          <p className="text-[9px] text-blue-600 uppercase font-semibold mb-1">Reading Velocity</p>
                          <p className="text-lg font-bold text-blue-900 font-mono">{st.reading_pace_per_week}</p>
                          <p className="text-[9px] text-blue-700">papers per week</p>
                        </div>
                        <div className="p-3 rounded-xl bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200">
                          <p className="text-[9px] text-purple-600 uppercase font-semibold mb-1">Active Days</p>
                          <p className="text-lg font-bold text-purple-900 font-mono">{st.days_since_join}</p>
                          <p className="text-[9px] text-purple-700">since joining</p>
                        </div>
                        {reportSnapshot.publications > 0 && (
                          <div className="p-3 rounded-xl bg-gradient-to-br from-green-50 to-green-100 border border-green-200">
                            <p className="text-[9px] text-green-600 uppercase font-semibold mb-1">Publications</p>
                            <p className="text-lg font-bold text-green-900 font-mono">{reportSnapshot.publications}</p>
                            <p className="text-[9px] text-green-700">{fmtCit(reportSnapshot.pub_citations)} citations</p>
                          </div>
                        )}
                        {profile.focus_topics.length > 0 && (
                          <div className="p-3 rounded-xl bg-gradient-to-br from-amber-50 to-amber-100 border border-amber-200">
                            <p className="text-[9px] text-amber-600 uppercase font-semibold mb-1">Focus Areas</p>
                            <p className="text-lg font-bold text-amber-900 font-mono">{profile.focus_topics.length}</p>
                            <p className="text-[9px] text-amber-700">research topics</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Focus Topics */}
                    {profile.focus_topics.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                          Research Interests
                        </p>
                        <div className="p-3 rounded-xl bg-white border border-gray-200 shadow-sm">
                          <div className="flex flex-wrap gap-1.5">
                            {profile.focus_topics.slice(0, 8).map(t => {
                              const c = getCatColor(t);
                              return (
                                <span key={t} className="px-2.5 py-1 rounded-lg text-[10px] font-semibold border shadow-sm" style={{ backgroundColor: c.fill, color: c.text, borderColor: c.border }}>
                                  {t.split('/').pop()}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Timestamp */}
                    <div className="text-center pt-2 border-t border-gray-200">
                      <span className="text-[9px] text-gray-400 font-mono">
                        Report generated {new Date(reportSnapshot.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                )}

                {/* Empty State */}
                {!reportSnapshot && !loading && (
                  <div className="text-center py-16">
                    <BarChart3 size={48} className="mx-auto text-gray-300 mb-3" />
                    <p className="text-sm text-gray-700 font-semibold mb-1">Create Your Research Report</p>
                    <p className="text-xs text-gray-500">
                      Select filters and generate insights into your reading journey
                    </p>
                  </div>
                )}
              </div>
            )}

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

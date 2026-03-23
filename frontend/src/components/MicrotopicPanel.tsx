import { useState, useEffect, useRef } from 'react';
import { X, Plus, Check, ExternalLink, FileBarChart2, Download, ArrowLeftRight, Loader2, BookOpen, Quote, Calendar, TrendingUp } from 'lucide-react';
import { getCatColor, fmtCit } from '../lib/colors';
import { api, type MicrotopicDetail, type Paper, type CompareRes, type GraphNode } from '../lib/api';

interface Props {
  microtopicId: string; allNodes: GraphNode[]; onClose: () => void;
  readingListIds: Set<string>; onAddToList: (id: string) => void; onRemoveFromList: (id: string) => void; userId: number;
  onCompareModeChange?: (isComparing: boolean) => void;
}

export function MicrotopicPanel({ microtopicId, allNodes, onClose, readingListIds, onAddToList, onRemoveFromList, onCompareModeChange }: Props) {
  const [detail, setDetail] = useState<MicrotopicDetail | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [paperTotal, setPaperTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'papers' | 'report'>('papers');
  const [compareId, setCompareId] = useState('');
  const [compareData, setCompareData] = useState<CompareRes | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [papersPage, setPapersPage] = useState(1);
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true); setDetail(null); setPapers([]); setTab('papers'); setCompareData(null); setPapersPage(1);
    onCompareModeChange?.(false); // Reset compare mode when switching microtopics
    Promise.all([
      api.getMicrotopic(microtopicId),
      api.getMicrotopicPapers(microtopicId, { page: 1, per_page: 20, sort_by: 'citation_count' }),
    ]).then(([d, p]) => { setDetail(d); setPapers(p.papers); setPaperTotal(p.total); })
      .catch(() => {}).finally(() => setLoading(false));
  }, [microtopicId, onCompareModeChange]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const loadMore = () => {
    const next = papersPage + 1;
    api.getMicrotopicPapers(microtopicId, { page: next, per_page: 20, sort_by: 'citation_count' })
      .then(p => { setPapers(prev => [...prev, ...p.papers]); setPapersPage(next); }).catch(() => {});
  };

  const runCompare = () => {
    if (!compareId) return;
    setReportLoading(true);
    api.compareMicrotopics(microtopicId, compareId).then(data => {
      setCompareData(data);
      onCompareModeChange?.(true);
    }).catch(() => {
      setCompareData(null);
      onCompareModeChange?.(false);
    }).finally(() => setReportLoading(false));
  };

  useEffect(() => {
    if (compareId) {
      setCompareData(null);
      onCompareModeChange?.(false);
    }
  }, [compareId, onCompareModeChange]);

  const exportPDF = () => {
    if (!detail) return;
    const cat = getCatColor(detail.bucket_value);
    const st = detail.stats;

    // Generate stats HTML
    const statsHtml = `
      <div class="stat-box"><div class="stat-label">Papers</div><div class="stat-value">${st.paper_count}</div></div>
      <div class="stat-box"><div class="stat-label">Total Cites</div><div class="stat-value">${fmtCit(st.total_citations)}</div></div>
      <div class="stat-box"><div class="stat-label">Avg Cites</div><div class="stat-value">${st.avg_citations?.toFixed(1) || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">Median</div><div class="stat-value">${fmtCit(st.median_citations)}</div></div>
      <div class="stat-box"><div class="stat-label">Max Cites</div><div class="stat-value">${fmtCit(st.max_citations)}</div></div>
      <div class="stat-box"><div class="stat-label">Growth</div><div class="stat-value">${Math.round(st.recent_growth_pct)}%</div></div>
      <div class="stat-box"><div class="stat-label">Span</div><div class="stat-value">${st.year_range || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">Authors</div><div class="stat-value">${st.unique_author_count != null ? fmtCit(st.unique_author_count) : '—'}</div></div>
    `;

    // Generate top papers HTML
    const topPapersHtml = detail.top_papers.length > 0 ? `
      <h2>Top Papers by Citations</h2>
      <table>
        <thead><tr><th style="width: 30px">#</th><th>Title</th><th style="text-align: right; width: 80px">Citations</th><th style="text-align: center; width: 60px">Year</th></tr></thead>
        <tbody>
          ${detail.top_papers.slice(0, 10).map((p, i) => `
            <tr>
              <td style="color: #9ca3af">${i + 1}</td>
              <td><strong>${p.title}</strong></td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${fmtCit(p.citation_count)}</td>
              <td style="text-align: center; color: #6b7280">${p.update_date ? String(p.update_date).slice(0, 4) : '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    ` : '';

    // Generate citation distribution HTML
    const citDistHtml = detail.citation_distribution.length > 0 ? `
      <h2>Citation Distribution</h2>
      <div class="dist-container">
        ${detail.citation_distribution.map((d: any) => {
          const max = Math.max(...detail.citation_distribution.map((x: any) => x.count), 1);
          const pct = ((d.count / st.paper_count) * 100).toFixed(0);
          const bucket = d.citation_bucket || d.bucket;
          return `
            <div class="dist-row">
              <span class="dist-label">${bucket} cites</span>
              <div class="dist-bar-container">
                <div class="dist-bar" style="width: ${(d.count / max) * 100}%; background: linear-gradient(90deg, ${cat.border} 0%, ${cat.border}cc 100%);"></div>
              </div>
              <span class="dist-value">${d.count} <span style="color: #9ca3af">(${pct}%)</span></span>
            </div>
          `;
        }).join('')}
      </div>
    ` : '';

    // Generate top authors HTML
    const topAuthorsHtml = detail.top_authors.length > 0 ? `
      <h2>Top Authors</h2>
      <div class="author-grid">
        ${detail.top_authors.slice(0, 12).map(a => `
          <div class="author-card">
            <div class="author-name">${a.name}</div>
            <div class="author-stats">${a.paper_count} paper${a.paper_count > 1 ? 's' : ''} · ${fmtCit(a.total_citations)} cites</div>
          </div>
        `).join('')}
      </div>
    ` : '';

    // Generate comparison HTML if applicable
    const compareHtml = compareData ? `
      <div class="compare-section">
        <h2>Comparison: ${detail.label} vs ${compareData.topic_b.label}</h2>
        <table>
          <thead>
            <tr>
              <th style="width: 25%">Metric</th>
              <th style="text-align: right; color: ${cat.text}">${detail.label}</th>
              <th style="text-align: right">${compareData.topic_b.label}</th>
              <th style="text-align: center; width: 100px">Difference</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Papers</strong></td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${st.paper_count}</td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${compareData.topic_b.stats.paper_count}</td>
              <td style="text-align: center; color: #6b7280">${Math.abs(st.paper_count - compareData.topic_b.stats.paper_count)}</td>
            </tr>
            <tr>
              <td><strong>Total Citations</strong></td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${fmtCit(st.total_citations)}</td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${fmtCit(compareData.topic_b.stats.total_citations)}</td>
              <td style="text-align: center; color: #6b7280">${fmtCit(Math.abs(st.total_citations - compareData.topic_b.stats.total_citations))}</td>
            </tr>
            <tr>
              <td><strong>Avg Citations</strong></td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${st.avg_citations.toFixed(1)}</td>
              <td style="text-align: right; font-family: 'JetBrains Mono', monospace">${compareData.topic_b.stats.avg_citations.toFixed(1)}</td>
              <td style="text-align: center; color: #6b7280">${Math.abs(st.avg_citations - compareData.topic_b.stats.avg_citations).toFixed(1)}</td>
            </tr>
          </tbody>
        </table>
        <div class="highlight-box">
          <strong>${compareData.overlap.shared_author_count}</strong> shared authors ·
          <strong>${compareData.overlap.shared_paper_count || 0}</strong> cross-citations
        </div>
      </div>
    ` : '';

    const w = window.open('', '_blank'); if (!w) return;
    w.document.write(`<!DOCTYPE html><html><head><title>${detail.label} Report</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: 'DM Sans', -apple-system, system-ui; color: #1f2937; padding: 40px; max-width: 900px; margin: 0 auto; font-size: 11px; background: #fafafa; line-height: 1.5; }
      .header { background: white; border: 1px solid #e5e7eb; padding: 32px; border-radius: 12px; margin-bottom: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
      h1 { font-family: 'Instrument Serif', serif; font-size: 32px; font-weight: 600; margin-bottom: 8px; color: #111827; }
      .subtitle { font-size: 14px; color: #6b7280; }
      .category-badge { display: inline-block; padding: 6px 14px; background: ${cat.fill}; color: ${cat.text}; border: 1px solid ${cat.border}; border-radius: 16px; font-size: 11px; font-weight: 600; margin-top: 12px; }
      h2 { font-size: 12px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.05em; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }
      .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
      .stat-box { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .stat-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; letter-spacing: 0.03em; }
      .stat-value { font-size: 22px; color: #111827; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
      table { width: 100%; border-collapse: collapse; margin: 12px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      th { text-align: left; padding: 10px 12px; background: #f9fafb; border-bottom: 2px solid #e5e7eb; font-weight: 700; color: #374151; font-size: 10px; text-transform: uppercase; letter-spacing: 0.03em; }
      td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6; color: #1f2937; font-size: 11px; }
      tbody tr:last-child td { border-bottom: none; }
      tbody tr:hover { background: #f9fafb; }
      .dist-container { background: white; padding: 16px; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .dist-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
      .dist-label { width: 90px; font-size: 10px; color: #6b7280; font-weight: 600; text-align: right; }
      .dist-bar-container { flex: 1; height: 24px; background: #f3f4f6; border-radius: 4px; overflow: hidden; }
      .dist-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
      .dist-value { width: 100px; font-size: 10px; color: #1f2937; font-weight: 600; font-family: 'JetBrains Mono', monospace; text-align: right; }
      .author-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
      .author-card { background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
      .author-name { font-weight: 600; color: #111827; font-size: 11px; margin-bottom: 4px; }
      .author-stats { font-size: 9px; color: #6b7280; }
      .highlight-box { background: linear-gradient(135deg, #dbeafe 0%, #e0e7ff 100%); border: 1px solid #93c5fd; border-radius: 8px; padding: 16px; margin: 16px 0; color: #1e40af; font-size: 12px; text-align: center; font-weight: 500; }
      .compare-section { background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #e5e7eb; }
      .footer { margin-top: 48px; padding-top: 20px; border-top: 2px solid #e5e7eb; font-size: 10px; color: #9ca3af; text-align: center; }
      strong { font-weight: 700; color: #111827; }
      @media print { body { padding: 20px; background: white; } .header { page-break-inside: avoid; } table { page-break-inside: avoid; } }
    </style></head><body>
    <div class="header">
      <h1>${detail.label}</h1>
      <div class="subtitle">${st.paper_count.toLocaleString()} papers · ${st.total_citations.toLocaleString()} total citations · ${st.year_range || 'N/A'}</div>
      <div class="category-badge">${detail.bucket_value}</div>
    </div>

    <h2>Overview Statistics</h2>
    <div class="stat-grid">${statsHtml}</div>

    ${compareHtml}
    ${topPapersHtml}
    ${citDistHtml}
    ${topAuthorsHtml}

    <div class="footer">
      Generated by <strong>ResearchViewer</strong> on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
    </div>
    </body></html>`);
    w.document.close(); setTimeout(() => w.print(), 500);
  };

  if (loading || !detail) return <div className="flex h-full items-center justify-center"><Loader2 size={20} className="animate-spin text-gray-400" /></div>;

  const cat = getCatColor(detail.bucket_value);
  const st = detail.stats;
  const otherNodes = allNodes.filter(n => n.id !== microtopicId);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-5 pb-3 border-b border-gray-100 shrink-0">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold mb-1.5 max-w-full truncate" style={{ backgroundColor: cat.fill, color: cat.text, border: `1px solid ${cat.border}40` }}>{detail.bucket_value}</span>
            <h2 className="text-base font-semibold text-gray-800 leading-snug break-words">{detail.label}</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 shrink-0"><X size={16} /></button>
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          <MM icon={<BookOpen size={9} />} label="Papers" value={String(st.paper_count)} />
          <MM icon={<Quote size={9} />} label="Avg" value={st.avg_citations != null ? st.avg_citations.toFixed(1) : '—'} />
          <MM icon={<TrendingUp size={9} />} label="Total" value={fmtCit(st.total_citations)} />
          <MM icon={<Calendar size={9} />} label="Span" value={st.year_range || '—'} />
        </div>
        <div className="flex gap-1 mt-3">
          <button onClick={() => setTab('papers')} className={`flex-1 py-1.5 rounded-lg text-xs font-medium ${tab === 'papers' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>Papers ({paperTotal})</button>
          <button onClick={() => setTab('report')} className={`flex-1 py-1.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1 ${tab === 'report' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}><FileBarChart2 size={11} /> Report</button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === 'papers' && (
          <div className="px-5 py-3 space-y-1.5">
            {detail.top_terms && detail.top_terms.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {detail.top_terms.slice(0, 8).map((t, i) => {
                  // Handle both string and object formats
                  let termName = typeof t === 'string' ? t : String(t);
                  // Remove confidence score and trailing punctuation (e.g., "kepler,0.8977..." -> "kepler")
                  termName = termName.replace(/[,\s0-9.]+$/, '').trim();
                  return <span key={i} className="px-2 py-0.5 rounded-full text-[9px] font-medium bg-gray-100 text-gray-500">{termName}</span>;
                })}
              </div>
            )}
            {papers.map(p => {
              const inList = readingListIds.has(p.id);
              const arxiv = p.id.match(/^\d{4}\./) ? `https://arxiv.org/abs/${p.id}` : null;
              return (
                <div key={p.id} className="group p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 hover:bg-gray-50/50">
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-700 leading-snug line-clamp-2">{p.title}</p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-[9px] text-gray-400 font-mono">{p.id}</span>
                        <span className="text-[9px] text-gray-400">{fmtCit(p.citation_count)}</span>
                        {p.update_date && <span className="text-[9px] text-gray-400">{String(p.update_date).slice(0, 4)}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-0.5 shrink-0">
                      {arxiv && <a href={arxiv} target="_blank" rel="noopener noreferrer" className="p-1 rounded text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100"><ExternalLink size={12} /></a>}
                      <button onClick={() => inList ? onRemoveFromList(p.id) : onAddToList(p.id)}
                        className={`p-1 rounded ${inList ? 'text-blue-500 bg-blue-50' : 'text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100'}`}>
                        {inList ? <Check size={12} /> : <Plus size={12} />}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
            {papers.length < paperTotal && (
              <button onClick={loadMore} className="w-full py-2 text-xs text-gray-400 hover:text-gray-600">Load more ({paperTotal - papers.length} remaining)</button>
            )}
          </div>
        )}

        {tab === 'report' && (
          <div className="px-5 py-4">
            <div className="mb-3 flex items-center gap-2">
              <label className="text-[9px] font-semibold text-gray-400 uppercase shrink-0">Compare</label>
              <select value={compareId} onChange={e => setCompareId(e.target.value)} className="flex-1 px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white focus:outline-none">
                <option value="">None</option>
                {otherNodes.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
              </select>
              {compareId && <button onClick={runCompare} disabled={reportLoading} className="px-2.5 py-1.5 rounded-lg bg-gray-800 text-white text-[10px] font-medium disabled:opacity-50"><ArrowLeftRight size={11} /></button>}
              <button onClick={exportPDF} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-medium text-white bg-gray-800 shrink-0"><Download size={10} /> PDF</button>
            </div>
            {reportLoading && <div className="py-8 flex justify-center"><Loader2 size={20} className="animate-spin text-gray-400" /></div>}
            {!reportLoading && (
              <div ref={reportRef} className="space-y-4">
                <div className="overflow-hidden">
                  <h1 className="break-words" style={{ fontFamily: "'Instrument Serif', serif", fontSize: '18px', color: '#1f2937' }}>{detail.label}</h1>
                  <p className="text-[10px] text-gray-400 mt-0.5 truncate">{detail.bucket_value} · {st.paper_count} papers · {new Date().toLocaleDateString()}</p>
                </div>
                {compareData ? (
                  <div>
                    <div className="flex items-center gap-2 mb-2 overflow-hidden">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold truncate max-w-[45%]" style={{ backgroundColor: cat.fill, color: cat.text }}>{detail.label}</span>
                      <ArrowLeftRight size={11} className="text-gray-400 shrink-0" />
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-600 truncate max-w-[45%]">{compareData.topic_b.label}</span>
                    </div>
                    <table className="w-full text-xs table-fixed"><thead><tr>
                      <th className="text-left py-1 px-2 text-[8px] text-gray-400 uppercase border-b-2 border-gray-200 w-[30%]">Metric</th>
                      <th className="text-right py-1 px-2 text-[8px] uppercase border-b-2 border-gray-200 truncate w-[35%]" style={{ color: cat.text }}>{detail.label}</th>
                      <th className="text-right py-1 px-2 text-[8px] text-gray-500 uppercase border-b-2 border-gray-200 truncate w-[35%]">{compareData.topic_b.label}</th>
                    </tr></thead><tbody>
                      <CR label="Papers" a={st.paper_count} b={compareData.topic_b.stats.paper_count} />
                      <CR label="Total Cites" a={st.total_citations} b={compareData.topic_b.stats.total_citations} />
                      <CR label="Avg Cites" a={parseFloat(st.avg_citations.toFixed(1))} b={parseFloat(compareData.topic_b.stats.avg_citations.toFixed(1))} />
                      <CR label="Median" a={st.median_citations} b={compareData.topic_b.stats.median_citations} />
                      <CR label="Max" a={st.max_citations} b={compareData.topic_b.stats.max_citations} />
                    </tbody></table>
                    <div className="mt-3 p-2.5 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-700">
                      <div className="flex items-center justify-center gap-4">
                        <div><span className="font-semibold">{compareData.overlap.shared_author_count}</span> shared authors</div>
                        <div><span className="font-semibold">{Math.abs(st.paper_count - compareData.topic_b.stats.paper_count)}</span> paper diff</div>
                        <div><span className="font-semibold">{Math.abs(st.avg_citations - compareData.topic_b.stats.avg_citations).toFixed(1)}</span> avg cite diff</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-4 gap-1.5">
                    <RC label="Papers" value={String(st.paper_count)} />
                    <RC label="Total" value={fmtCit(st.total_citations)} />
                    <RC label="Avg" value={st.avg_citations != null ? st.avg_citations.toFixed(1) : '—'} />
                    <RC label="Median" value={fmtCit(st.median_citations)} />
                    <RC label="Max" value={fmtCit(st.max_citations)} />
                    <RC label="Growth" value={`${Math.round(st.recent_growth_pct)}%`} />
                    <RC label="Span" value={st.year_range || '—'} />
                    <RC label="Authors" value={st.unique_author_count != null ? fmtCit(st.unique_author_count) : '—'} />
                  </div>
                )}
                {detail.papers_by_year.length > 0 && (<div className="overflow-visible">
                  <p className="text-[9px] font-semibold text-gray-400 uppercase mb-1.5">Citations by Year</p>
                  <div className="overflow-visible">
                    <SvgBar data={detail.papers_by_year.map(d => ({ label: d.year.toString().slice(-2), value: d.total_citations }))} color={cat.border} height={80} />
                  </div>
                </div>)}
                {detail.papers_by_year.length > 0 && (<div className="overflow-visible">
                  <p className="text-[9px] font-semibold text-gray-400 uppercase mb-1.5">Papers per Year</p>
                  <div className="overflow-visible">
                    <SvgBar data={detail.papers_by_year.map(d => ({ label: d.year.toString().slice(-2), value: d.count }))} color="#64748b" height={50} />
                  </div>
                </div>)}
                {detail.citation_distribution.length > 0 && (<div>
                  <p className="text-[9px] font-semibold text-gray-400 uppercase mb-1.5">Citation Distribution <span className="text-gray-300 normal-case font-normal">(# of papers by citation count)</span></p>
                  <div className="space-y-1">{detail.citation_distribution.map((d: any) => {
                    const max = Math.max(...detail.citation_distribution.map((x: any) => x.count), 1);
                    const pct = ((d.count / st.paper_count) * 100).toFixed(0);
                    const bucket = d.citation_bucket || d.bucket;
                    return (<div key={bucket} className="flex items-center gap-2">
                      <span className="w-16 text-right text-[9px] text-gray-500 font-mono shrink-0" title="Citation range">{bucket}</span>
                      <div className="flex-1 h-3.5 bg-gray-100 rounded overflow-hidden"><div className="h-full rounded" style={{ width: `${(d.count / max) * 100}%`, backgroundColor: cat.border + 'cc' }} /></div>
                      <span className="w-12 text-[9px] text-gray-400 font-mono" title={`${d.count} papers (${pct}%)`}>{d.count} ({pct}%)</span>
                    </div>);
                  })}</div>
                </div>)}
                {detail.top_papers.length > 0 && (<div>
                  <p className="text-[9px] font-semibold text-gray-400 uppercase mb-1.5">Top Papers</p>
                  <table className="w-full text-[10px]"><thead><tr>
                    <th className="text-left py-1 px-1 text-[8px] text-gray-400 uppercase border-b-2 border-gray-200">#</th>
                    <th className="text-left py-1 px-1 text-[8px] text-gray-400 uppercase border-b-2 border-gray-200">Title</th>
                    <th className="text-right py-1 px-1 text-[8px] text-gray-400 uppercase border-b-2 border-gray-200">Cites</th>
                  </tr></thead><tbody>
                    {detail.top_papers.slice(0, 8).map((p, i) => (
                      <tr key={p.id}><td className="py-1 px-1 text-gray-400 font-mono">{i + 1}</td>
                        <td className="py-1 px-1 text-gray-700 max-w-[220px] truncate">{p.title}</td>
                        <td className="py-1 px-1 text-right text-gray-600 font-mono">{fmtCit(p.citation_count)}</td></tr>))}
                  </tbody></table>
                </div>)}
                {detail.top_authors.length > 0 && (<div>
                  <p className="text-[9px] font-semibold text-gray-400 uppercase mb-1.5">Authors</p>
                  <div className="flex flex-wrap gap-1">{detail.top_authors.slice(0, 10).map(a => (
                    <span key={a.name} className="px-2 py-0.5 rounded-full text-[9px] font-medium bg-gray-100 text-gray-600 border border-gray-200">{a.name} ({a.paper_count})</span>
                  ))}</div>
                </div>)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MM({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (<div className="p-1.5 rounded-lg bg-gray-50 border border-gray-100 text-center">
    <div className="flex items-center justify-center gap-0.5 text-gray-400 mb-0.5">{icon}<span className="text-[7px] uppercase tracking-wider">{label}</span></div>
    <p className="text-xs font-bold text-gray-800 font-mono tabular-nums">{value}</p></div>);
}
function RC({ label, value }: { label: string; value: string }) {
  return (<div className="p-2 rounded-lg bg-gray-50 border border-gray-100"><p className="text-[7px] text-gray-400 uppercase">{label}</p><p className="text-sm font-bold text-gray-800 font-mono mt-0.5">{value}</p></div>);
}
function CR({ label, a, b }: { label: string; a: number; b: number }) {
  const w = a > b ? 'a' : b > a ? 'b' : '';
  return (<tr><td className="py-1 px-2 text-gray-600 text-xs">{label}</td>
    <td className={`py-1 px-2 text-right font-mono text-xs ${w === 'a' ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}>{a.toLocaleString()}</td>
    <td className={`py-1 px-2 text-right font-mono text-xs ${w === 'b' ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}>{b.toLocaleString()}</td></tr>);
}
function SvgBar({ data, color, height = 80 }: { data: { label: string; value: number }[]; color: string; height?: number }) {
  if (!data.length) return null;
  const max = Math.max(...data.map(d => d.value), 1);
  const bw = Math.max(8, Math.min(22, (340 - data.length * 2) / data.length));
  const leftPadding = 42; // More space for Y-axis labels
  const totalWidth = data.length * (bw + 3) + leftPadding + 5;

  // Y-axis ticks (5 levels)
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(pct => ({
    y: height - (pct * height),
    label: Math.round(pct * max).toLocaleString()
  }));

  return (<div className="overflow-visible -ml-2"><svg width={totalWidth} height={height + 18} className="overflow-visible">
    {/* Y-axis */}
    <line x1={leftPadding - 5} y1={0} x2={leftPadding - 5} y2={height} stroke="#e5e7eb" strokeWidth={1} />
    {yTicks.map((tick, i) => (
      <g key={i}>
        <line x1={leftPadding - 8} y1={tick.y} x2={leftPadding - 5} y2={tick.y} stroke="#9ca3af" strokeWidth={1} />
        <text x={leftPadding - 10} y={tick.y + 3} textAnchor="end" fontSize={7} fill="#9ca3af">{tick.label}</text>
      </g>
    ))}

    {/* Bars */}
    {data.map((d, i) => { const h2 = (d.value / max) * height; return (<g key={i}>
      <rect x={leftPadding + i * (bw + 3)} y={height - h2} width={bw} height={Math.max(h2, 1)} rx={2} fill={color} opacity={0.8} />
      <title>{d.label}: {d.value.toLocaleString()}</title>
      <text x={leftPadding + i * (bw + 3) + bw / 2} y={height + 12} textAnchor="middle" fontSize={7} fill="#9ca3af">{d.label}</text></g>); })}
  </svg></div>);
}

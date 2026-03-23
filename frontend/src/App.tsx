import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { GraphView, type GraphLevel } from './components/GraphView';
import { MicrotopicPanel } from './components/MicrotopicPanel';
import { RightSidebar } from './components/RightSidebar';
import { SearchDialog } from './components/SearchDialog';
import { UserProfilePanel } from './components/UserProfilePanel';
import { AboutPanel } from './components/AboutPanel';
import { StatsBar } from './components/StatsBar';
import { api, type DomainEntry, type TopicEntry, type GraphNode, type GraphEdge } from './lib/api';

const USER_ID = 1;

interface DrillState {
  level: GraphLevel;
  domain: string | null;  // selected domain name
  topic: string | null;   // selected topic name
}

export default function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [paperCount, setPaperCount] = useState<number | null>(null);
  const [username, setUsername] = useState<string>('');

  // Drill state
  const [drill, setDrill] = useState<DrillState>({ level: 'domain', domain: null, topic: null });

  // Level 1 data
  const [domains, setDomains] = useState<DomainEntry[]>([]);
  // Level 2 data
  const [topics, setTopics] = useState<TopicEntry[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  // Level 3 data
  const [microNodes, setMicroNodes] = useState<GraphNode[]>([]);
  const [microEdges, setMicroEdges] = useState<GraphEdge[]>([]);
  const [microLoading, setMicroLoading] = useState(false);

  // Selected microtopic for detail panel
  const [selectedMicro, setSelectedMicro] = useState<string | null>(null);
  const [isComparing, setIsComparing] = useState(false);

  // Reading list
  const [readingListIds, setReadingListIds] = useState<Set<string>>(new Set());

  // Dialogs
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);

  // Right sidebar resizing
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);

  // Left panel (microtopic) resizing
  const [leftPanelWidth, setLeftPanelWidth] = useState(480);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [isResizingLeft, setIsResizingLeft] = useState(false);

  // ── Bootstrap ──────────────────────────────────────────────
  useEffect(() => {
    api.health().then(h => { setApiOnline(true); setPaperCount(h.paper_count); }).catch(() => setApiOnline(false));
    api.getDomains(100).then(d => setDomains(d.domains)).catch(() => {});
    api.getReadingList(USER_ID).then(d => setReadingListIds(new Set(d.papers.map(p => p.id)))).catch(() => {});
    api.getUser(USER_ID).then(u => setUsername(u.username)).catch(() => {});
  }, []);

  // ── Drill handlers ─────────────────────────────────────────
  const drillIntoDomain = useCallback((domain: string) => {
    setDrill({ level: 'topic', domain, topic: null });
    setSelectedMicro(null);
    setTopicsLoading(true);
    api.getTopicsInDomain(domain, 100)
      .then(d => setTopics(d.topics))
      .catch(() => setTopics([]))
      .finally(() => setTopicsLoading(false));
  }, []);

  const drillIntoTopic = useCallback((topic: string) => {
    setDrill(prev => ({ ...prev, level: 'micro', topic }));
    setSelectedMicro(null);
    setMicroLoading(true);
    // Use the topic name as bucket_value for microtopic graph
    // The microtopic graph endpoint filters by bucket_value
    api.microtopicGraph({ bucket_value: topic, min_size: 2, limit: 80 })
      .then(d => { setMicroNodes(d.nodes); setMicroEdges(d.edges); })
      .catch(() => { setMicroNodes([]); setMicroEdges([]); })
      .finally(() => setMicroLoading(false));
  }, []);

  const drillBack = useCallback(() => {
    setSelectedMicro(null);
    if (drill.level === 'micro') {
      setDrill(prev => ({ ...prev, level: 'topic', topic: null }));
      setMicroNodes([]); setMicroEdges([]);
    } else if (drill.level === 'topic') {
      setDrill({ level: 'domain', domain: null, topic: null });
      setTopics([]);
    }
  }, [drill.level]);

  // ── Reading list ───────────────────────────────────────────
  const addToList = useCallback((id: string) => {
    setReadingListIds(prev => new Set(prev).add(id));
    api.addToReadingList(USER_ID, id).catch(() => setReadingListIds(prev => { const n = new Set(prev); n.delete(id); return n; }));
  }, []);
  const removeFromList = useCallback((id: string) => {
    setReadingListIds(prev => { const n = new Set(prev); n.delete(id); return n; });
    api.removeFromReadingList(USER_ID, id).catch(() => setReadingListIds(prev => new Set(prev).add(id)));
  }, []);
  const markAsRead = useCallback((id: string) => {
    api.markAsRead(USER_ID, id).then(() => {
      // Optionally remove from reading list after marking as read
      removeFromList(id);
    }).catch(err => console.error('Failed to mark as read:', err));
  }, [removeFromList]);

  // ── Keyboard shortcut ──────────────────────────────────────
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setSearchOpen(true); } };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);

  // ── Sidebar resize handlers ────────────────────────────────
  const handleResizeStart = useCallback(() => {
    setIsResizing(true);
  }, []);

  const handleLeftResizeStart = useCallback(() => {
    setIsResizingLeft(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= 200 && newWidth <= 600) {
        setSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    if (!isResizingLeft) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = e.clientX;
      if (newWidth >= 300 && newWidth <= 800) {
        setLeftPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizingLeft(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingLeft]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header onSearch={() => setSearchOpen(true)} onProfile={() => setProfileOpen(true)} apiOnline={apiOnline} readCount={readingListIds.size} username={username} />

      <div className="flex flex-1 overflow-hidden">
        {selectedMicro && !leftPanelCollapsed && (
          <div
            className="shrink-0 border-r border-gray-200/80 bg-white relative flex"
            style={{ width: isComparing ? `${leftPanelWidth * 1.4}px` : `${leftPanelWidth}px` }}
          >
            {/* Resize handle - left edge, hanging outward */}
            <div className="absolute -left-3 top-0 bottom-0 w-6 flex items-center justify-center z-50 group">
              <div
                onMouseDown={handleLeftResizeStart}
                className="px-1 py-2 bg-white border border-gray-300 rounded flex items-center gap-0.5 cursor-col-resize opacity-0 group-hover:opacity-100 hover:bg-gray-50 transition-opacity shadow-sm"
              >
                <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
                <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
                <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
              </div>
            </div>
            <div className="flex-1 overflow-x-hidden">
              <MicrotopicPanel microtopicId={selectedMicro} allNodes={microNodes} onClose={() => { setSelectedMicro(null); setLeftPanelCollapsed(false); }}
                readingListIds={readingListIds} onAddToList={addToList} onRemoveFromList={removeFromList} userId={USER_ID}
                onCompareModeChange={setIsComparing} />
            </div>
          </div>
        )}

        <div className="flex-1 relative min-w-0">
          <GraphView
            level={drill.level}
            domains={domains}
            topics={topics}
            topicsLoading={topicsLoading}
            microNodes={microNodes}
            microEdges={microEdges}
            microLoading={microLoading}
            drillDomain={drill.domain}
            drillTopic={drill.topic}
            selectedMicro={selectedMicro}
            onDomainClick={drillIntoDomain}
            onTopicClick={drillIntoTopic}
            onMicroClick={setSelectedMicro}
            onBack={drillBack}
          />
        </div>

        {/* Right sidebar with resize handle */}
        {!sidebarCollapsed ? (
          <div
            className="shrink-0 border-l border-gray-200/80 bg-white relative flex"
            style={{ width: `${sidebarWidth}px` }}
          >
            {/* Resize handle - left edge, hanging outward */}
            <div className="absolute -left-3 top-0 bottom-0 w-6 flex items-center justify-center z-50 group">
              <div
                onMouseDown={handleResizeStart}
                className="px-1 py-2 bg-white border border-gray-300 rounded flex items-center gap-0.5 cursor-col-resize opacity-0 group-hover:opacity-100 hover:bg-gray-50 transition-opacity shadow-sm"
              >
                <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
                <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
                <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
              </div>
            </div>
            <div className="flex-1 overflow-hidden">

            {/* Close button */}
            <button
              onClick={() => setSidebarCollapsed(true)}
              className="absolute right-2 top-1 z-10 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              title="Collapse sidebar"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>

              <RightSidebar userId={USER_ID} readingListIds={readingListIds} onRemoveFromList={removeFromList} onAddToList={addToList} onMarkAsRead={markAsRead} />
            </div>
          </div>
        ) : (
          /* Collapsed sidebar - reopening tab */
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="shrink-0 w-8 bg-white border-l border-gray-200/80 hover:bg-gray-50 transition-colors flex items-center justify-center group"
            title="Expand sidebar"
          >
            <svg className="w-4 h-4 text-gray-400 group-hover:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        )}
      </div>

      <StatsBar paperCount={paperCount} drill={drill} microNodeCount={microNodes.length} microEdgeCount={microEdges.length} topicCount={topics.length} domainCount={domains.length} apiOnline={apiOnline} onAboutClick={() => setAboutOpen(true)} />

      {searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} onAddToList={addToList} onMarkAsRead={markAsRead} readingListIds={readingListIds} />}
      {profileOpen && <UserProfilePanel userId={USER_ID} onClose={() => setProfileOpen(false)} />}
      {aboutOpen && <AboutPanel onClose={() => setAboutOpen(false)} />}
    </div>
  );
}

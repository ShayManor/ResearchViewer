import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { GraphView, type GraphLevel } from './components/GraphView';
import { MicrotopicPanel } from './components/MicrotopicPanel';
import { RightSidebar } from './components/RightSidebar';
import { SearchDialog } from './components/SearchDialog';
import { UserProfilePanel } from './components/UserProfilePanel';
import { AboutPanel } from './components/AboutPanel';
import { StatsBar } from './components/StatsBar';
import { api, type DomainEntry, type TopicEntry, type GraphNode, type GraphEdge, type VelocityRes } from './lib/api';

const USER_ID = 1;

interface DrillState {
  level: GraphLevel;
  domain: string | null;  // selected domain name
  topic: string | null;   // selected topic name
}

export default function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [paperCount, setPaperCount] = useState<number | null>(null);
  const [velocity, setVelocity] = useState<VelocityRes | null>(null);
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

  // ── Bootstrap ──────────────────────────────────────────────
  useEffect(() => {
    api.health().then(h => { setApiOnline(true); setPaperCount(h.paper_count); }).catch(() => setApiOnline(false));
    api.getDomains(100).then(d => setDomains(d.domains)).catch(() => {});
    api.velocity('week', 12).then(setVelocity).catch(() => {});
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

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header onSearch={() => setSearchOpen(true)} onProfile={() => setProfileOpen(true)} apiOnline={apiOnline} readCount={readingListIds.size} username={username} />

      <div className="flex flex-1 overflow-hidden">
        {selectedMicro && (
          <div className={`${isComparing ? 'w-[680px]' : 'w-[480px]'} shrink-0 border-r border-gray-200/80 overflow-x-hidden bg-white transition-all duration-300`}>
            <MicrotopicPanel microtopicId={selectedMicro} allNodes={microNodes} onClose={() => setSelectedMicro(null)}
              readingListIds={readingListIds} onAddToList={addToList} onRemoveFromList={removeFromList} userId={USER_ID}
              onCompareModeChange={setIsComparing} />
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

        <div className="w-[300px] shrink-0 border-l border-gray-200/80 overflow-hidden bg-white">
          <RightSidebar userId={USER_ID} readingListIds={readingListIds} onRemoveFromList={removeFromList} onAddToList={addToList} velocity={velocity} onMarkAsRead={markAsRead} />
        </div>
      </div>

      <StatsBar paperCount={paperCount} drill={drill} microNodeCount={microNodes.length} microEdgeCount={microEdges.length} topicCount={topics.length} domainCount={domains.length} velocity={velocity} apiOnline={apiOnline} onAboutClick={() => setAboutOpen(true)} />

      {searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} onAddToList={addToList} onMarkAsRead={markAsRead} readingListIds={readingListIds} />}
      {profileOpen && <UserProfilePanel userId={USER_ID} onClose={() => setProfileOpen(false)} />}
      {aboutOpen && <AboutPanel onClose={() => setAboutOpen(false)} />}
    </div>
  );
}

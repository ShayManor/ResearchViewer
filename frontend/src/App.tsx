import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { GraphView } from './components/GraphView';
import { MicrotopicPanel } from './components/MicrotopicPanel';
import { RightSidebar } from './components/RightSidebar';
import { SearchDialog } from './components/SearchDialog';
import { UserProfilePanel } from './components/UserProfilePanel';
import { StatsBar } from './components/StatsBar';
import { api, type SubjectEntry, type GraphNode, type GraphEdge, type VelocityRes } from './lib/api';

// Hardcoded user ID — replace with auth when ready
const USER_ID = 1;

export default function App() {
  // API state
  const [apiOnline, setApiOnline] = useState(false);
  const [paperCount, setPaperCount] = useState<number | null>(null);
  const [subjects, setSubjects] = useState<SubjectEntry[]>([]);
  const [velocity, setVelocity] = useState<VelocityRes | null>(null);

  // Graph drill-down: null = subjects level, string = microtopics for that subject
  const [drillSubject, setDrillSubject] = useState<string | null>(null);
  const [microNodes, setMicroNodes] = useState<GraphNode[]>([]);
  const [microEdges, setMicroEdges] = useState<GraphEdge[]>([]);
  const [microLoading, setMicroLoading] = useState(false);

  // Selected microtopic
  const [selectedMicrotopicId, setSelectedMicrotopicId] = useState<string | null>(null);

  // Reading list DOIs (just IDs, for quick membership checks)
  const [readingListIds, setReadingListIds] = useState<Set<string>>(new Set());

  // Dialogs
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  // ── Bootstrap ──────────────────────────────────────────────
  useEffect(() => {
    api.health()
      .then(h => { setApiOnline(true); setPaperCount(h.paper_count); })
      .catch(() => setApiOnline(false));
    api.subjects(15).then(d => setSubjects(d.subjects)).catch(() => {});
    api.velocity('week', 12).then(setVelocity).catch(() => {});
    // Load reading list IDs
    api.getReadingList(USER_ID).then(d => {
      setReadingListIds(new Set(d.papers.map(p => p.id)));
    }).catch(() => {});
  }, []);

  // ── Drill into microtopics for a subject ───────────────────
  const drillInto = useCallback((subject: string) => {
    setDrillSubject(subject);
    setSelectedMicrotopicId(null);
    setMicroLoading(true);
    api.microtopicGraph({ bucket_value: subject, min_size: 3, limit: 60 })
      .then(d => { setMicroNodes(d.nodes); setMicroEdges(d.edges); })
      .catch(() => { setMicroNodes([]); setMicroEdges([]); })
      .finally(() => setMicroLoading(false));
  }, []);

  const drillBack = useCallback(() => {
    setDrillSubject(null);
    setSelectedMicrotopicId(null);
    setMicroNodes([]);
    setMicroEdges([]);
  }, []);

  // ── Reading list mutations ─────────────────────────────────
  const addToList = useCallback((paperId: string) => {
    setReadingListIds(prev => new Set(prev).add(paperId));
    api.addToReadingList(USER_ID, paperId).catch(() => {
      setReadingListIds(prev => { const n = new Set(prev); n.delete(paperId); return n; });
    });
  }, []);

  const removeFromList = useCallback((paperId: string) => {
    setReadingListIds(prev => { const n = new Set(prev); n.delete(paperId); return n; });
    api.removeFromReadingList(USER_ID, paperId).catch(() => {
      setReadingListIds(prev => new Set(prev).add(paperId));
    });
  }, []);

  // ── Keyboard shortcut ──────────────────────────────────────
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setSearchOpen(true); } };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header
        onSearch={() => setSearchOpen(true)}
        onProfile={() => setProfileOpen(true)}
        apiOnline={apiOnline}
        readCount={readingListIds.size}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left: microtopic detail when selected */}
        {selectedMicrotopicId && (
          <div className="w-[420px] shrink-0 border-r border-gray-200/80 overflow-hidden bg-white animate-slide-in">
            <MicrotopicPanel
              microtopicId={selectedMicrotopicId}
              allNodes={microNodes}
              onClose={() => setSelectedMicrotopicId(null)}
              readingListIds={readingListIds}
              onAddToList={addToList}
              onRemoveFromList={removeFromList}
              userId={USER_ID}
            />
          </div>
        )}

        {/* Center: graph */}
        <div className="flex-1 relative min-w-0">
          <GraphView
            subjects={subjects}
            drillSubject={drillSubject}
            microNodes={microNodes}
            microEdges={microEdges}
            microLoading={microLoading}
            selectedMicrotopicId={selectedMicrotopicId}
            onSubjectClick={drillInto}
            onMicrotopicClick={setSelectedMicrotopicId}
            onBack={drillBack}
          />
        </div>

        {/* Right: reading list / hot / recs */}
        <div className="w-[300px] shrink-0 border-l border-gray-200/80 overflow-hidden bg-white">
          <RightSidebar
            userId={USER_ID}
            readingListIds={readingListIds}
            onRemoveFromList={removeFromList}
            onAddToList={addToList}
            velocity={velocity}
          />
        </div>
      </div>

      <StatsBar
        paperCount={paperCount}
        subjects={subjects}
        drillSubject={drillSubject}
        microNodeCount={microNodes.length}
        microEdgeCount={microEdges.length}
        velocity={velocity}
        apiOnline={apiOnline}
      />

      {searchOpen && (
        <SearchDialog
          onClose={() => setSearchOpen(false)}
          onAddToList={addToList}
          readingListIds={readingListIds}
        />
      )}
      {profileOpen && (
        <UserProfilePanel userId={USER_ID} onClose={() => setProfileOpen(false)} />
      )}
    </div>
  );
}

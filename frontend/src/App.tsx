import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { TopicGraph } from './components/TopicGraph';
import { TopicDetailPanel } from './components/TopicDetailPanel';
import { RightSidebar } from './components/RightSidebar';
import { SearchDialog } from './components/SearchDialog';
import { UserProfilePanel } from './components/UserProfilePanel';
import { api } from './lib/api';
import {
  DUMMY_USER, buildTopicGraph, getRecommendations, SEED_PAPERS,
  type TopicNode, type TopicEdge, type UserProfileData, type Publication,
} from './lib/dummy-data';

export default function App() {
  const [topicNodes, setTopicNodes] = useState<TopicNode[]>([]);
  const [topicEdges, setTopicEdges] = useState<TopicEdge[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<TopicNode | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [user, setUser] = useState<UserProfileData>(DUMMY_USER);
  const [recommendations, setRecommendations] = useState<ReturnType<typeof getRecommendations>>([]);
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    const { nodes, edges } = buildTopicGraph();
    setTopicNodes(nodes);
    setTopicEdges(edges);
  }, []);

  useEffect(() => {
    api.health().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
  }, []);

  useEffect(() => {
    setRecommendations(getRecommendations(user.readingList));
  }, [user.readingList]);

  const addToReadingList = useCallback((doi: string) => {
    setUser(prev => {
      if (prev.readingList.includes(doi)) return prev;
      return {
        ...prev,
        readingList: [...prev.readingList, doi],
        readHistory: [...prev.readHistory, { doi, readDate: new Date().toISOString().slice(0, 10) }],
      };
    });
  }, []);

  const removeFromReadingList = useCallback((doi: string) => {
    setUser(prev => ({
      ...prev,
      readingList: prev.readingList.filter(d => d !== doi),
    }));
  }, []);

  const linkAuthor = useCallback((authorId: string, authorName: string) => {
    setUser(prev => ({ ...prev, linkedAuthorId: authorId, linkedAuthorName: authorName }));
  }, []);

  const unlinkAuthor = useCallback(() => {
    setUser(prev => ({ ...prev, linkedAuthorId: null, linkedAuthorName: null }));
  }, []);

  const addPublication = useCallback((pub: Publication) => {
    setUser(prev => ({ ...prev, publications: [...prev.publications, pub] }));
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header
        username={user.username}
        onSearch={() => setSearchOpen(true)}
        onProfile={() => setProfileOpen(true)}
        apiOnline={apiOnline}
        readCount={user.readingList.length}
      />

      <div className="flex flex-1 overflow-hidden">
        {selectedTopic && (
          <div className="w-[420px] shrink-0 border-r border-gray-200/80 overflow-hidden bg-white animate-slide-in">
            <TopicDetailPanel
              topic={selectedTopic}
              allTopics={topicNodes}
              onClose={() => setSelectedTopic(null)}
              readingList={user.readingList}
              onAddToList={addToReadingList}
              onRemoveFromList={removeFromReadingList}
            />
          </div>
        )}

        <div className="flex-1 relative min-w-0">
          <TopicGraph
            nodes={topicNodes}
            edges={topicEdges}
            selectedTopicId={selectedTopic?.id || null}
            onTopicClick={n => setSelectedTopic(prev => prev?.id === n.id ? null : n)}
          />
        </div>

        <div className="w-[300px] shrink-0 border-l border-gray-200/80 overflow-hidden bg-white">
          <RightSidebar
            readingList={user.readingList}
            recommendations={recommendations}
            onRemoveFromList={removeFromReadingList}
            onAddToList={addToReadingList}
          />
        </div>
      </div>

      {searchOpen && (
        <SearchDialog onClose={() => setSearchOpen(false)} onSelectPaper={p => {
          setSearchOpen(false);
          const cat = p.categories?.split(/\s+/)[0];
          if (cat) { const t = topicNodes.find(x => x.id === cat); if (t) setSelectedTopic(t); }
        }} onAddToList={addToReadingList} readingList={user.readingList} />
      )}

      {profileOpen && (
        <UserProfilePanel
          user={user}
          onClose={() => setProfileOpen(false)}
          onLinkAuthor={linkAuthor}
          onUnlinkAuthor={unlinkAuthor}
          onAddPublication={addPublication}
        />
      )}
    </div>
  );
}

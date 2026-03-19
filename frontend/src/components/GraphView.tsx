import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3-force';
import { ZoomIn, ZoomOut, RotateCcw, ArrowLeft, Loader2 } from 'lucide-react';
import { getCatColor, domainRadius, topicRadius, microRadius } from '../lib/colors';
import type { DomainEntry, TopicEntry, GraphNode, GraphEdge } from '../lib/api';

export type GraphLevel = 'domain' | 'topic' | 'micro';

interface Props {
  level: GraphLevel;
  domains: DomainEntry[];
  topics: TopicEntry[];
  topicsLoading: boolean;
  microNodes: GraphNode[];
  microEdges: GraphEdge[];
  microLoading: boolean;
  drillDomain: string | null;
  drillTopic: string | null;
  selectedMicro: string | null;
  onDomainClick: (domain: string) => void;
  onTopicClick: (topic: string) => void;
  onMicroClick: (id: string) => void;
  onBack: () => void;
}

interface SN { id: string; label: string; size: number; extra?: any; x?: number; y?: number; vx?: number; vy?: number; }
interface SL { source: string | SN; target: string | SN; weight: number; }

const MIN_Z = 0.15, MAX_Z = 3, DRAG_T = 6;

export function GraphView({
  level, domains, topics, topicsLoading, microNodes, microEdges, microLoading,
  drillDomain, drillTopic, selectedMicro,
  onDomainClick, onTopicClick, onMicroClick, onBack,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [h, setH] = useState(0);
  const [simNodes, setSimNodes] = useState<SN[]>([]);
  const [simLinks, setSimLinks] = useState<SL[]>([]);
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [ready, setReady] = useState(false);

  // Refs for pointer handling
  const isPan = useRef(false);
  const panS = useRef({ x: 0, y: 0 }), panO = useRef({ x: 0, y: 0 });
  const dragId = useRef<string | null>(null);
  const dragP = useRef({ x: 0, y: 0 }), dragN = useRef({ x: 0, y: 0 });
  const dragMoved = useRef(false);
  const snRef = useRef(simNodes); snRef.current = simNodes;
  const zRef = useRef(zoom); zRef.current = zoom;

  // ── Measure container (ResizeObserver + immediate fallback) ─
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Immediate measure to avoid the "no render until inspect" bug
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setW(rect.width);
      setH(rect.height);
    }
    const ro = new ResizeObserver(entries => {
      const r = entries[0].contentRect;
      if (r.width > 0 && r.height > 0) { setW(r.width); setH(r.height); }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── Build sim data from current level ──────────────────────
  // Use a generation counter to force re-simulation
  const [simGen, setSimGen] = useState(0);

  useEffect(() => {
    let nodes: SN[] = [];
    let links: SL[] = [];

    if (level === 'domain') {
      nodes = domains.map(d => ({ id: d.domain, label: d.domain, size: d.paper_count, extra: d }));
    } else if (level === 'topic') {
      nodes = topics.map(t => ({ id: t.topic, label: t.topic, size: t.paper_count, extra: t }));
    } else {
      nodes = microNodes.map(n => ({ id: n.id, label: n.label, size: n.size, extra: n }));
      const ids = new Set(nodes.map(n => n.id));
      links = microEdges.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ source: e.source, target: e.target, weight: e.weight }));
    }

    setSimNodes(nodes);
    setSimLinks(links);
    setReady(false);
    setSimGen(g => g + 1);
  }, [level, domains, topics, microNodes, microEdges]);

  // ── Run d3-force simulation ────────────────────────────────
  useEffect(() => {
    if (w === 0 || h === 0 || simNodes.length === 0) return;
    // Always re-run when simGen changes (which happens when data changes)

    const rFn = level === 'domain' ? domainRadius : level === 'topic' ? topicRadius : microRadius;

    const sim = d3.forceSimulation(simNodes)
      .force('charge', d3.forceManyBody().strength(level === 'domain' ? -1500 : level === 'topic' ? -800 : -500))
      .force('collide', d3.forceCollide<SN>().radius(d => rFn(d.size) + 15))
      .force('x', d3.forceX(w / 2).strength(0.04))
      .force('y', d3.forceY(h / 2).strength(0.04));

    if (simLinks.length > 0) {
      sim.force('link', d3.forceLink<SN, SL>(simLinks).id(d => d.id)
        .distance(d => 300 - (d.weight || 0) * 200)
        .strength(d => 0.2 + (d.weight || 0) * 0.8));
    }

    sim.stop();
    for (let i = 0; i < 300; i++) sim.tick();

    // Auto-fit
    const xs = simNodes.filter(n => n.x != null).map(n => n.x!);
    const ys = simNodes.filter(n => n.y != null).map(n => n.y!);
    if (xs.length > 0) {
      const pad = 100;
      const [mnX, mxX, mnY, mxY] = [Math.min(...xs) - pad, Math.max(...xs) + pad, Math.min(...ys) - pad, Math.max(...ys) + pad];
      const gw = mxX - mnX, gh = mxY - mnY;
      const fz = Math.min(w / gw, h / gh, 1.1);
      const cx = (mnX + mxX) / 2, cy = (mnY + mxY) / 2;
      setZoom(fz);
      setPan({ x: w / 2 - cx * fz - (w / 2) * (1 - fz), y: h / 2 - cy * fz - (h / 2) * (1 - fz) });
    }

    setSimNodes([...simNodes]);
    setReady(true);
    return () => { sim.stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [w, h, simGen]);

  // ── Node map for edge rendering ────────────────────────────
  const nodeMap = useMemo(() => { const m = new Map<string, SN>(); simNodes.forEach(n => m.set(n.id, n)); return m; }, [simNodes]);
  const maxWeight = useMemo(() => Math.max(...simLinks.map(l => l.weight || 0), 0.01), [simLinks]);

  // ── Pointer handlers ───────────────────────────────────────
  const handleWheel = useCallback((e: React.WheelEvent) => { e.preventDefault(); setZoom(z => Math.min(MAX_Z, Math.max(MIN_Z, z * (e.deltaY > 0 ? 0.92 : 1.08)))); }, []);

  const handleDown = useCallback((e: React.PointerEvent) => {
    const el = (e.target as HTMLElement).closest('[data-nid]');
    if (el) {
      const id = el.getAttribute('data-nid')!;
      const n = snRef.current.find(x => x.id === id);
      if (!n || n.x == null || n.y == null) return;
      dragId.current = id; dragP.current = { x: e.clientX, y: e.clientY }; dragN.current = { x: n.x, y: n.y };
      dragMoved.current = false;
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      return;
    }
    isPan.current = true; panS.current = { x: e.clientX, y: e.clientY }; panO.current = { x: pan.x, y: pan.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [pan]);

  const handleMove = useCallback((e: React.PointerEvent) => {
    if (dragId.current) {
      const dx = e.clientX - dragP.current.x, dy = e.clientY - dragP.current.y;
      if (!dragMoved.current && Math.sqrt(dx * dx + dy * dy) < DRAG_T) return;
      dragMoved.current = true;
      const z = zRef.current;
      const nx = dragN.current.x + dx / z, ny = dragN.current.y + dy / z;
      const id = dragId.current;
      setSimNodes(p => p.map(n => n.id === id ? { ...n, x: nx, y: ny } : n));
      return;
    }
    if (!isPan.current) return;
    setPan({ x: panO.current.x + (e.clientX - panS.current.x), y: panO.current.y + (e.clientY - panS.current.y) });
  }, []);

  const nodeClickHandler = useCallback((id: string) => {
    if (level === 'domain') onDomainClick(id);
    else if (level === 'topic') onTopicClick(id);
    else onMicroClick(id);
  }, [level, onDomainClick, onTopicClick, onMicroClick]);

  const handleUp = useCallback(() => {
    if (dragId.current) {
      if (!dragMoved.current) nodeClickHandler(dragId.current);
      dragId.current = null;
      return;
    }
    isPan.current = false;
  }, [nodeClickHandler]);

  const rFn = level === 'domain' ? domainRadius : level === 'topic' ? topicRadius : microRadius;
  const isLoading = (level === 'topic' && topicsLoading) || (level === 'micro' && microLoading);
  const showBackBtn = level !== 'domain';

  // ── Breadcrumb text ────────────────────────────────────────
  const breadcrumb = level === 'topic' && drillDomain
    ? drillDomain
    : level === 'micro' && drillTopic
      ? `${drillDomain} › ${drillTopic}`
      : null;

  return (
    <div ref={containerRef} className="relative w-full h-full overflow-hidden bg-gradient-to-br from-[#fafafa] via-white to-gray-50/50"
      onWheel={handleWheel} onPointerDown={handleDown} onPointerMove={handleMove} onPointerUp={handleUp} onPointerLeave={handleUp}
      style={{ touchAction: 'none' }}>

      {/* Dot grid */}
      <div className="absolute inset-0 opacity-[0.10] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle, #94a3b8 0.8px, transparent 0.8px)', backgroundSize: '28px 28px' }} />

      {/* Back + breadcrumb */}
      {showBackBtn && (
        <button onClick={onBack} className="absolute top-4 left-4 z-20 flex items-center gap-2 px-3 py-2 rounded-xl bg-white/90 border border-gray-200 backdrop-blur-md text-sm font-medium text-gray-600 hover:bg-gray-100 transition-all shadow-sm">
          <ArrowLeft size={15} />
          <span>Back</span>
          {breadcrumb && <span className="ml-1 text-[10px] text-gray-400 max-w-[200px] truncate">{breadcrumb}</span>}
        </button>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-2"><Loader2 size={24} className="text-gray-400 animate-spin" />
            <p className="text-sm text-gray-500">Loading {level === 'topic' ? 'topics' : 'microtopics'}…</p>
          </div>
        </div>
      )}

      {/* Empty state */}
      {ready && simNodes.length === 0 && !isLoading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-sm text-gray-400">No data available for this level</p>
        </div>
      )}

      {/* Transform layer */}
      <div className="absolute inset-0 origin-center" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
        {/* Edges (micro level only) */}
        {level === 'micro' && (
          <svg className="absolute inset-0 pointer-events-none" style={{ overflow: 'visible', width: '100%', height: '100%' }}>
            {simLinks.map((link, i) => {
              const sId = typeof link.source === 'object' ? (link.source as SN).id : link.source;
              const tId = typeof link.target === 'object' ? (link.target as SN).id : link.target;
              const s = nodeMap.get(sId), t = nodeMap.get(tId);
              if (!s || !t || s.x == null || t.x == null || s.y == null || t.y == null) return null;
              const isSel = selectedMicro && (sId === selectedMicro || tId === selectedMicro);
              const nw = (link.weight || 0) / maxWeight;
              const sw = 1 + nw * 5;
              const op = selectedMicro ? (isSel ? 0.5 + nw * 0.5 : 0.04) : 0.08 + nw * 0.55;
              const dash = nw < 0.3 ? '4 4' : nw < 0.6 ? '8 3' : 'none';
              return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke={isSel ? '#3b82f6' : '#64748b'} strokeWidth={isSel ? sw + 1 : sw} opacity={op}
                strokeLinecap="round" strokeDasharray={isSel ? 'none' : dash} style={{ transition: 'opacity 0.3s' }} />;
            })}
          </svg>
        )}

        {/* Nodes */}
        <div className="absolute inset-0 pointer-events-none">
          {simNodes.map(node => {
            if (node.x == null || node.y == null) return null;
            const r = rFn(node.size);
            const colorKey = level === 'domain' ? node.label : level === 'topic' ? (drillDomain || '') : (node.extra?.bucket_value || '');
            const cat = getCatColor(colorKey);
            const isSel = level === 'micro' && node.id === selectedMicro;
            const isDim = level === 'micro' && selectedMicro && !isSel;

            // Label: use full label, let CSS handle wrapping and truncation
            const displayLabel = node.label;
            // Font size: smaller to fit more text across multiple lines
            const fontSize = level === 'domain'
              ? Math.min(11, Math.max(8, r / 5))
              : level === 'topic'
                ? Math.min(9, Math.max(7, r / 5.5))
                : Math.min(11, Math.max(8, r / 5));

            return (
              <div key={node.id} data-nid={node.id}
                className="absolute rounded-full flex flex-col items-center justify-center cursor-pointer pointer-events-auto select-none"
                style={{
                  width: r * 2, height: r * 2, left: node.x - r, top: node.y - r,
                  background: isSel ? `linear-gradient(135deg, ${cat.border}25, ${cat.border}10)` : `linear-gradient(145deg, ${cat.fill}, white)`,
                  border: `2.5px solid ${isSel ? cat.border : cat.border + '80'}`,
                  boxShadow: isSel ? `0 0 24px ${cat.border}40, 0 6px 20px rgba(0,0,0,0.08)` : '0 3px 12px rgba(0,0,0,0.06)',
                  opacity: isDim ? 0.2 : 1,
                  transform: isSel ? 'scale(1.12)' : 'scale(1)',
                  transition: 'opacity 0.3s, transform 0.25s, box-shadow 0.25s',
                }}>
                {/* Gloss */}
                <div className="absolute rounded-full pointer-events-none" style={{ top: '8%', left: '15%', width: '50%', height: '30%', background: 'linear-gradient(180deg, rgba(255,255,255,0.6) 0%, transparent 100%)' }} />
                {/* Label */}
                <span className="font-sans font-bold leading-tight text-center px-1.5 break-words" style={{ fontSize: `${fontSize}px`, color: cat.text, maxWidth: r * 2 - 10, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: level === 'domain' ? 4 : level === 'topic' ? 5 : 6, WebkitBoxOrient: 'vertical' as any }}>
                  {displayLabel}
                </span>
                {/* Count */}
                <span className="font-mono tabular-nums leading-none mt-0.5" style={{ fontSize: '8px', color: cat.text + 'aa' }}>
                  {node.size >= 1_000_000 ? (node.size / 1_000_000).toFixed(1) + 'M' : node.size >= 1000 ? (node.size / 1000).toFixed(0) + 'k' : node.size}
                </span>
                {/* Growth badge */}
                {level === 'micro' && node.extra?.recent_growth_pct > 30 && (
                  <div className="absolute -top-1 -right-1 px-1 py-0.5 rounded-full bg-emerald-500 text-white text-[7px] font-bold leading-none">
                    ↑{Math.round(node.extra.recent_growth_pct)}%
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Zoom controls */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 z-10">
        <button onClick={() => setZoom(z => Math.min(MAX_Z, z * 1.25))} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md"><ZoomIn size={16} /></button>
        <button onClick={() => setZoom(z => Math.max(MIN_Z, z * 0.8))} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md"><ZoomOut size={16} /></button>
        <button onClick={() => { setZoom(0.85); setPan({ x: 0, y: 0 }); }} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md"><RotateCcw size={16} /></button>
      </div>

      {/* Level label - only show for domain and topic levels */}
      {level !== 'micro' && (
        <div className="absolute bottom-4 left-4 p-3 rounded-xl bg-white/80 border border-gray-200/80 backdrop-blur-md z-10">
          <p className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider mb-1">
            {level === 'domain' ? 'Domains' : 'Topics'}
          </p>
          <p className="text-[10px] text-gray-500">
            {level === 'domain' ? 'Click a domain to see its topics' : 'Click a topic to see microtopics'}
          </p>
        </div>
      )}
    </div>
  );
}

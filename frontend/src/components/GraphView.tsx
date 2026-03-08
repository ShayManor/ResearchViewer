import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3-force';
import { ZoomIn, ZoomOut, RotateCcw, ArrowLeft, Loader2 } from 'lucide-react';
import { getCatColor, subjectNodeRadius, nodeRadius } from '../lib/colors';
import type { SubjectEntry, GraphNode, GraphEdge } from '../lib/api';

interface Props {
  subjects: SubjectEntry[];
  drillSubject: string | null;
  microNodes: GraphNode[];
  microEdges: GraphEdge[];
  microLoading: boolean;
  selectedMicrotopicId: string | null;
  onSubjectClick: (subject: string) => void;
  onMicrotopicClick: (id: string) => void;
  onBack: () => void;
}

// Simulation node
interface SN { id: string; label: string; size: number; extra?: any; x?: number; y?: number; vx?: number; vy?: number; }
interface SL { source: string | SN; target: string | SN; weight: number; }

const MIN_Z = 0.25, MAX_Z = 3, DRAG_T = 6;

export function GraphView({ subjects, drillSubject, microNodes, microEdges, microLoading, selectedMicrotopicId, onSubjectClick, onMicrotopicClick, onBack }: Props) {
  const cRef = useRef<HTMLDivElement>(null);
  const [bounds, setBounds] = useState({ width: 0, height: 0 });
  const [simNodes, setSimNodes] = useState<SN[]>([]);
  const [simLinks, setSimLinks] = useState<SL[]>([]);
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [ready, setReady] = useState(false);
  const isPan = useRef(false);
  const panS = useRef({ x: 0, y: 0 }), panO = useRef({ x: 0, y: 0 });
  const posC = useRef<Map<string, { x: number; y: number }>>(new Map());
  const dragId = useRef<string | null>(null), dragP = useRef({ x: 0, y: 0 }), dragN = useRef({ x: 0, y: 0 }), dragMoved = useRef(false);
  const snRef = useRef(simNodes); snRef.current = simNodes;
  const zRef = useRef(zoom); zRef.current = zoom;

  // Measure
  useEffect(() => { const el = cRef.current; if (!el) return; const ro = new ResizeObserver(e => { const r = e[0].contentRect; setBounds({ width: r.width, height: r.height }); }); ro.observe(el); return () => ro.disconnect(); }, []);

  // Build sim data when level changes
  const isSubjectLevel = drillSubject === null;

  useEffect(() => {
    posC.current.clear();
    setReady(false);

    if (isSubjectLevel) {
      // Subject nodes
      const nodes: SN[] = subjects.map(s => ({ id: s.subject, label: s.subject, size: s.paper_count, extra: s }));
      setSimNodes(nodes);
      setSimLinks([]); // no edges between subjects at top level
    } else {
      const nodes: SN[] = microNodes.map(n => ({ id: n.id, label: n.label, size: n.size, extra: n }));
      const ids = new Set(nodes.map(n => n.id));
      const links: SL[] = microEdges.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ source: e.source, target: e.target, weight: e.weight }));
      setSimNodes(nodes);
      setSimLinks(links);
    }
  }, [isSubjectLevel, subjects, microNodes, microEdges]);

  // Run simulation
  useEffect(() => {
    if (!bounds.width || !bounds.height || !simNodes.length) return;
    if (simNodes.every(n => n.x != null && n.y != null) && ready) return;

    const radiusFn = isSubjectLevel ? (n: SN) => subjectNodeRadius(n.size) : (n: SN) => nodeRadius(n.size);

    const sim = d3.forceSimulation(simNodes)
      .force('charge', d3.forceManyBody().strength(isSubjectLevel ? -1200 : -600))
      .force('collide', d3.forceCollide<SN>().radius(d => radiusFn(d) + 20))
      .force('x', d3.forceX(bounds.width / 2).strength(0.05))
      .force('y', d3.forceY(bounds.height / 2).strength(0.05));

    if (!isSubjectLevel && simLinks.length > 0) {
      sim.force('link', d3.forceLink<SN, SL>(simLinks).id(d => d.id)
        .distance(d => 350 - (d.weight || 0) * 250)
        .strength(d => 0.2 + (d.weight || 0) * 0.8));
    }

    sim.stop();
    for (let i = 0; i < 300; i++) sim.tick();

    for (const n of simNodes) {
      if (n.x != null && n.y != null) posC.current.set(n.id, { x: n.x, y: n.y });
    }

    // Auto-fit
    const xs = simNodes.filter(n => n.x != null).map(n => n.x!), ys = simNodes.filter(n => n.y != null).map(n => n.y!);
    if (xs.length) {
      const pad = 80;
      const [mnX, mxX, mnY, mxY] = [Math.min(...xs) - pad, Math.max(...xs) + pad, Math.min(...ys) - pad, Math.max(...ys) + pad];
      const fz = Math.min(bounds.width / (mxX - mnX), bounds.height / (mxY - mnY), 1.2);
      const cx = (mnX + mxX) / 2, cy = (mnY + mxY) / 2;
      setZoom(fz);
      setPan({ x: bounds.width / 2 - cx * fz - (bounds.width / 2) * (1 - fz), y: bounds.height / 2 - cy * fz - (bounds.height / 2) * (1 - fz) });
    }
    setSimNodes([...simNodes]);
    setReady(true);
    return () => { sim.stop(); };
  }, [bounds.width, bounds.height, simNodes.length, simLinks.length, isSubjectLevel]);

  const nodeMap = useMemo(() => { const m = new Map<string, SN>(); simNodes.forEach(n => m.set(n.id, n)); return m; }, [simNodes]);
  const maxWeight = useMemo(() => Math.max(...simLinks.map(l => l.weight || 0), 0.01), [simLinks]);

  // Event handlers
  const handleWheel = useCallback((e: React.WheelEvent) => { e.preventDefault(); setZoom(z => Math.min(MAX_Z, Math.max(MIN_Z, z * (e.deltaY > 0 ? 0.92 : 1.08)))); }, []);

  const handleDown = useCallback((e: React.PointerEvent) => {
    const el = (e.target as HTMLElement).closest('[data-nid]');
    if (el) {
      const id = el.getAttribute('data-nid')!;
      const n = snRef.current.find(x => x.id === id);
      if (!n || n.x == null) return;
      dragId.current = id; dragP.current = { x: e.clientX, y: e.clientY }; dragN.current = { x: n.x, y: n.y! }; dragMoved.current = false;
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); return;
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
      posC.current.set(dragId.current, { x: nx, y: ny });
      const id = dragId.current;
      setSimNodes(p => p.map(n => n.id === id ? { ...n, x: nx, y: ny } : n));
      return;
    }
    if (!isPan.current) return;
    setPan({ x: panO.current.x + (e.clientX - panS.current.x), y: panO.current.y + (e.clientY - panS.current.y) });
  }, []);

  const handleUp = useCallback(() => {
    if (dragId.current) {
      if (!dragMoved.current) {
        const id = dragId.current;
        if (isSubjectLevel) onSubjectClick(id);
        else onMicrotopicClick(id);
      }
      dragId.current = null; return;
    }
    isPan.current = false;
  }, [isSubjectLevel, onSubjectClick, onMicrotopicClick]);

  const handleReset = useCallback(() => { setZoom(0.85); setPan({ x: 0, y: 0 }); }, []);

  const radiusFn = isSubjectLevel ? subjectNodeRadius : nodeRadius;

  return (
    <div ref={cRef} className="relative w-full h-full overflow-hidden bg-gradient-to-br from-[#fafafa] via-white to-gray-50/50"
      onWheel={handleWheel} onPointerDown={handleDown} onPointerMove={handleMove} onPointerUp={handleUp} onPointerLeave={handleUp} style={{ touchAction: 'none' }}>

      {/* Dot grid */}
      <div className="absolute inset-0 opacity-[0.12] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle, #94a3b8 0.8px, transparent 0.8px)', backgroundSize: '28px 28px' }} />

      {/* Back button when drilled in */}
      {drillSubject && (
        <button onClick={onBack} className="absolute top-4 left-4 z-20 flex items-center gap-2 px-3 py-2 rounded-xl bg-white/90 border border-gray-200 backdrop-blur-md text-sm font-medium text-gray-600 hover:bg-gray-100 transition-all shadow-sm">
          <ArrowLeft size={15} />
          <span>Back to subjects</span>
          <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] font-semibold" style={{ backgroundColor: getCatColor(drillSubject).fill, color: getCatColor(drillSubject).text }}>{drillSubject}</span>
        </button>
      )}

      {/* Loading overlay */}
      {microLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-2"><Loader2 size={24} className="text-gray-400 animate-spin" /><p className="text-sm text-gray-500">Loading microtopics…</p></div>
        </div>
      )}

      {/* Transform layer */}
      <div className="absolute inset-0 origin-center" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
        {/* Edges (microtopic level only) */}
        {!isSubjectLevel && (
          <svg className="absolute inset-0 pointer-events-none" style={{ overflow: 'visible', width: '100%', height: '100%' }}>
            {simLinks.map((link, i) => {
              const sId = typeof link.source === 'object' ? (link.source as SN).id : link.source;
              const tId = typeof link.target === 'object' ? (link.target as SN).id : link.target;
              const s = nodeMap.get(sId), t = nodeMap.get(tId);
              if (!s || !t || s.x == null || t.x == null || s.y == null || t.y == null) return null;
              const isSel = selectedMicrotopicId && (sId === selectedMicrotopicId || tId === selectedMicrotopicId);
              const w = (link.weight || 0) / maxWeight;
              const sw = 1 + w * 5;
              const op = selectedMicrotopicId ? (isSel ? 0.5 + w * 0.5 : 0.04) : 0.08 + w * 0.55;
              const dash = w < 0.3 ? '4 4' : w < 0.6 ? '8 3' : 'none';
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
            const r = radiusFn(node.size);
            const cat = getCatColor(isSubjectLevel ? node.id : (node.extra?.bucket_value || ''));
            const isSel = !isSubjectLevel && node.id === selectedMicrotopicId;
            const isDim = !isSubjectLevel && selectedMicrotopicId && !isSel;

            return (
              <div key={node.id} data-nid={node.id}
                className="absolute rounded-full flex flex-col items-center justify-center cursor-pointer pointer-events-auto select-none"
                style={{
                  width: r * 2, height: r * 2, left: node.x - r, top: node.y - r,
                  background: isSel ? `linear-gradient(135deg, ${cat.border}25, ${cat.border}10)` : `linear-gradient(145deg, ${cat.fill}, white)`,
                  border: `2.5px solid ${isSel ? cat.border : cat.border + '80'}`,
                  boxShadow: isSel ? `0 0 24px ${cat.border}40, 0 6px 20px rgba(0,0,0,0.08)` : '0 3px 12px rgba(0,0,0,0.06)',
                  opacity: isDim ? 0.2 : 1,
                  transform: isSel ? 'scale(1.15)' : 'scale(1)',
                  transition: 'opacity 0.3s, transform 0.25s, box-shadow 0.25s',
                }}>
                <div className="absolute rounded-full pointer-events-none" style={{ top: '8%', left: '15%', width: '50%', height: '30%', background: 'linear-gradient(180deg, rgba(255,255,255,0.6) 0%, transparent 100%)' }} />
                <span className="font-sans font-bold leading-tight text-center px-1.5" style={{ fontSize: r > 34 ? '11px' : r > 26 ? '9px' : '8px', color: cat.text }}>
                  {node.label.length > 20 && r < 34 ? node.label.slice(0, 18) + '…' : node.label}
                </span>
                <span className="font-mono tabular-nums leading-none mt-0.5" style={{ fontSize: '8px', color: cat.text + 'aa' }}>
                  {node.size >= 1000 ? (node.size / 1000).toFixed(0) + 'k' : node.size}
                </span>
                {/* Growth badge for microtopics */}
                {!isSubjectLevel && node.extra?.recent_growth_pct > 30 && (
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
        <button onClick={() => setZoom(z => Math.min(MAX_Z, z * 1.25))} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md transition-colors"><ZoomIn size={16} /></button>
        <button onClick={() => setZoom(z => Math.max(MIN_Z, z * 0.8))} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md transition-colors"><ZoomOut size={16} /></button>
        <button onClick={handleReset} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md transition-colors"><RotateCcw size={16} /></button>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 p-3 rounded-xl bg-white/80 border border-gray-200/80 backdrop-blur-md z-10">
        {isSubjectLevel ? (
          <p className="text-[9px] text-gray-400">Click a subject to explore its microtopics</p>
        ) : (
          <>
            <p className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Edge strength</p>
            <div className="flex items-center gap-3 text-[10px] text-gray-500">
              <div className="flex items-center gap-1"><svg width={18} height={4}><line x1={0} y1={2} x2={18} y2={2} stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="4 4" /></svg><span>Weak</span></div>
              <div className="flex items-center gap-1"><svg width={18} height={4}><line x1={0} y1={2} x2={18} y2={2} stroke="#94a3b8" strokeWidth={2.5} strokeDasharray="8 3" /></svg><span>Mid</span></div>
              <div className="flex items-center gap-1"><svg width={18} height={6}><line x1={0} y1={3} x2={18} y2={3} stroke="#64748b" strokeWidth={4} /></svg><span>Strong</span></div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

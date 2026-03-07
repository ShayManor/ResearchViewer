import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3-force';
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { getCategoryColor, getNodeRadius } from '../lib/colors';
import type { TopicNode, TopicEdge } from '../lib/dummy-data';

interface Props { nodes: TopicNode[]; edges: TopicEdge[]; selectedTopicId: string | null; onTopicClick: (n: TopicNode) => void; }
interface SimNode extends TopicNode { x?: number; y?: number; vx?: number; vy?: number; index?: number; }
interface SimLink { source: string | SimNode; target: string | SimNode; weight: number; sharedPaperCount: number; }

const MIN_ZOOM = 0.3, MAX_ZOOM = 3, DRAG_THRESHOLD = 6;

export function TopicGraph({ nodes, edges, selectedTopicId, onTopicClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [bounds, setBounds] = useState({ width: 0, height: 0 });
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [simLinks, setSimLinks] = useState<SimLink[]>([]);
  const [ready, setReady] = useState(false);
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });
  const panOff = useRef({ x: 0, y: 0 });
  const posCache = useRef<Map<string, { x: number; y: number }>>(new Map());
  const origPos = useRef<Map<string, { x: number; y: number }>>(new Map());
  const dragId = useRef<string | null>(null);
  const dragPtr = useRef({ x: 0, y: 0 });
  const dragNode = useRef({ x: 0, y: 0 });
  const dragged = useRef(false);
  const snRef = useRef(simNodes); snRef.current = simNodes;
  const zRef = useRef(zoom); zRef.current = zoom;
  const cbRef = useRef(onTopicClick); cbRef.current = onTopicClick;

  useEffect(() => { const el = containerRef.current; if (!el) return; const ro = new ResizeObserver(e => { const r = e[0].contentRect; setBounds({ width: r.width, height: r.height }); }); ro.observe(el); return () => ro.disconnect(); }, []);

  useEffect(() => {
    if (!nodes.length) return;
    const nc: SimNode[] = nodes.map(n => { const c = posCache.current.get(n.id); return { ...n, ...(c ? { x: c.x, y: c.y } : {}) }; });
    const ids = new Set(nc.map(n => n.id));
    setSimNodes(nc);
    setSimLinks(edges.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ ...e })));
  }, [nodes, edges]);

  useEffect(() => {
    if (!bounds.width || !bounds.height || !simNodes.length) return;
    if (simNodes.every(n => n.x != null && n.y != null) && ready) return;
    const sim = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id(d => d.id)
        .distance(d => 350 - (d.weight || 0) * 250)
        .strength(d => 0.2 + (d.weight || 0) * 0.8))
      .force('charge', d3.forceManyBody().strength(-900))
      .force('collide', d3.forceCollide<SimNode>().radius(d => getNodeRadius(d.paperCount) + 25))
      .force('x', d3.forceX(bounds.width / 2).strength(0.04))
      .force('y', d3.forceY(bounds.height / 2).strength(0.04));
    sim.stop(); for (let i = 0; i < 300; i++) sim.tick();
    const first = origPos.current.size === 0;
    for (const n of simNodes) { if (n.x != null && n.y != null) { posCache.current.set(n.id, { x: n.x, y: n.y }); if (first) origPos.current.set(n.id, { x: n.x, y: n.y }); } }
    const xs = simNodes.filter(n => n.x != null).map(n => n.x!), ys = simNodes.filter(n => n.y != null).map(n => n.y!);
    if (xs.length) { const pad = 80; const [mnX, mxX, mnY, mxY] = [Math.min(...xs) - pad, Math.max(...xs) + pad, Math.min(...ys) - pad, Math.max(...ys) + pad]; const fz = Math.min(bounds.width / (mxX - mnX), bounds.height / (mxY - mnY), 1.2); const cx = (mnX + mxX) / 2, cy = (mnY + mxY) / 2; setZoom(fz); setPan({ x: bounds.width / 2 - cx * fz - (bounds.width / 2) * (1 - fz), y: bounds.height / 2 - cy * fz - (bounds.height / 2) * (1 - fz) }); }
    setSimNodes([...simNodes]); setReady(true);
    return () => { sim.stop(); };
  }, [bounds.width, bounds.height, simNodes.length]);

  const nodeMap = useMemo(() => { const m = new Map<string, SimNode>(); simNodes.forEach(n => m.set(n.id, n)); return m; }, [simNodes]);
  const handleWheel = useCallback((e: React.WheelEvent) => { e.preventDefault(); setZoom(z => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * (e.deltaY > 0 ? 0.92 : 1.08)))); }, []);
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    const el = (e.target as HTMLElement).closest('[data-node-id]');
    if (el) { const id = el.getAttribute('data-node-id'); if (!id) return; const n = snRef.current.find(x => x.id === id); if (!n || n.x == null) return; dragId.current = id; dragPtr.current = { x: e.clientX, y: e.clientY }; dragNode.current = { x: n.x, y: n.y! }; dragged.current = false; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); return; }
    isPanning.current = true; panStart.current = { x: e.clientX, y: e.clientY }; panOff.current = { x: pan.x, y: pan.y }; (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [pan]);
  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (dragId.current) { const dx = e.clientX - dragPtr.current.x, dy = e.clientY - dragPtr.current.y; if (!dragged.current && Math.sqrt(dx * dx + dy * dy) < DRAG_THRESHOLD) return; dragged.current = true; const z = zRef.current; const nx = dragNode.current.x + dx / z, ny = dragNode.current.y + dy / z; posCache.current.set(dragId.current, { x: nx, y: ny }); const id = dragId.current; setSimNodes(p => p.map(n => n.id === id ? { ...n, x: nx, y: ny } : n)); return; }
    if (!isPanning.current) return; setPan({ x: panOff.current.x + (e.clientX - panStart.current.x), y: panOff.current.y + (e.clientY - panStart.current.y) });
  }, []);
  const handlePointerUp = useCallback(() => { if (dragId.current) { if (!dragged.current) { const n = snRef.current.find(x => x.id === dragId.current); if (n) cbRef.current(n); } dragId.current = null; return; } isPanning.current = false; }, []);
  const handleReset = useCallback(() => { if (origPos.current.size) { posCache.current = new Map(origPos.current); setSimNodes(p => p.map(n => { const pos = origPos.current.get(n.id); return pos ? { ...n, x: pos.x, y: pos.y } : n; })); } setZoom(0.85); setPan({ x: 0, y: 0 }); }, []);

  // Max weight for normalization
  const maxWeight = useMemo(() => Math.max(...edges.map(e => e.weight), 0.01), [edges]);

  return (
    <div ref={containerRef} className="relative w-full h-full overflow-hidden bg-gradient-to-br from-[#fafafa] via-white to-gray-50/50"
      onWheel={handleWheel} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerLeave={handlePointerUp} style={{ touchAction: 'none' }}>
      <div className="absolute inset-0 opacity-[0.12] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle, #94a3b8 0.8px, transparent 0.8px)', backgroundSize: '28px 28px' }} />

      <div className="absolute inset-0 origin-center" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
        <svg className="absolute inset-0 pointer-events-none" style={{ overflow: 'visible', width: '100%', height: '100%' }}>
          {simLinks.map((link, i) => {
            const sId = typeof link.source === 'object' ? (link.source as SimNode).id : link.source;
            const tId = typeof link.target === 'object' ? (link.target as SimNode).id : link.target;
            const s = nodeMap.get(sId), t = nodeMap.get(tId);
            if (!s || !t || s.x == null || t.x == null || s.y == null || t.y == null) return null;
            const isSel = selectedTopicId && (sId === selectedTopicId || tId === selectedTopicId);
            const w = (link.weight || 0) / maxWeight; // normalized 0-1
            const strokeW = 1 + w * 5;
            const opacity = selectedTopicId ? (isSel ? 0.5 + w * 0.5 : 0.04) : 0.08 + w * 0.55;
            // Dashed for weak edges, solid for strong
            const dashArray = w < 0.3 ? '4 4' : w < 0.6 ? '8 3' : 'none';
            return (
              <g key={i}>
                <line x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                  stroke={isSel ? '#3b82f6' : '#64748b'}
                  strokeWidth={isSel ? strokeW + 1 : strokeW}
                  opacity={opacity} strokeLinecap="round" strokeDasharray={isSel ? 'none' : dashArray}
                  style={{ transition: 'opacity 0.3s, stroke 0.3s' }} />
                {/* Weight label on hover — show shared count */}
                {isSel && link.sharedPaperCount > 0 && (
                  <text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 8}
                    textAnchor="middle" fontSize={10} fill="#3b82f6" fontWeight={600} fontFamily="var(--font-mono, monospace)">
                    {link.sharedPaperCount} shared
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        <div className="absolute inset-0 pointer-events-none">
          {simNodes.map(node => {
            if (node.x == null || node.y == null) return null;
            const r = getNodeRadius(node.paperCount);
            const cat = getCategoryColor(node.id);
            const isSel = node.id === selectedTopicId;
            const isDim = selectedTopicId && !isSel;
            const growth = node.recentGrowth;
            return (
              <div key={node.id} data-node-id={node.id}
                className="absolute rounded-full flex flex-col items-center justify-center cursor-pointer pointer-events-auto select-none"
                style={{ width: r * 2, height: r * 2, left: node.x - r, top: node.y - r,
                  background: isSel ? `linear-gradient(135deg, ${cat.border}25, ${cat.border}10)` : `linear-gradient(145deg, ${cat.fill}, white)`,
                  border: `2.5px solid ${isSel ? cat.border : cat.border + '80'}`,
                  boxShadow: isSel ? `0 0 24px ${cat.border}40, 0 6px 20px rgba(0,0,0,0.08)` : '0 3px 12px rgba(0,0,0,0.06)',
                  opacity: isDim ? 0.2 : 1, transform: isSel ? 'scale(1.15)' : 'scale(1)',
                  transition: 'opacity 0.3s, transform 0.25s, box-shadow 0.25s',
                }}>
                <div className="absolute rounded-full pointer-events-none" style={{ top: '8%', left: '15%', width: '50%', height: '30%', background: 'linear-gradient(180deg, rgba(255,255,255,0.6) 0%, transparent 100%)' }} />
                <span className="font-sans font-bold leading-tight text-center px-1" style={{ fontSize: r > 34 ? '12px' : '10px', color: cat.text }}>{node.label}</span>
                <span className="font-mono tabular-nums leading-none mt-0.5" style={{ fontSize: '9px', color: cat.text + 'aa' }}>{node.paperCount} papers</span>
                {/* Growth indicator */}
                {growth > 0.3 && (
                  <div className="absolute -top-1 -right-1 px-1 py-0.5 rounded-full bg-emerald-500 text-white text-[7px] font-bold leading-none">
                    ↑{Math.round(growth * 100)}%
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 z-10">
        <button onClick={() => setZoom(z => Math.min(MAX_ZOOM, z * 1.25))} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md transition-colors"><ZoomIn size={16} /></button>
        <button onClick={() => setZoom(z => Math.max(MIN_ZOOM, z * 0.8))} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md transition-colors"><ZoomOut size={16} /></button>
        <button onClick={handleReset} className="p-2 rounded-lg bg-white/80 hover:bg-gray-100 text-gray-400 border border-gray-200/80 backdrop-blur-md transition-colors"><RotateCcw size={16} /></button>
      </div>

      <div className="absolute bottom-4 left-4 p-3 rounded-xl bg-white/80 border border-gray-200/80 backdrop-blur-md z-10">
        <p className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Edge strength</p>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <div className="flex items-center gap-1"><svg width={20} height={4}><line x1={0} y1={2} x2={20} y2={2} stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="4 4" /></svg><span>Weak</span></div>
          <div className="flex items-center gap-1"><svg width={20} height={4}><line x1={0} y1={2} x2={20} y2={2} stroke="#94a3b8" strokeWidth={2.5} strokeDasharray="8 3" /></svg><span>Medium</span></div>
          <div className="flex items-center gap-1"><svg width={20} height={6}><line x1={0} y1={3} x2={20} y2={3} stroke="#64748b" strokeWidth={4} /></svg><span>Strong</span></div>
        </div>
        <p className="text-[9px] text-gray-400 mt-2">Click a topic to explore papers</p>
      </div>
    </div>
  );
}

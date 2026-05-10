import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft, RefreshCw, ZoomIn, ZoomOut, Maximize2,
  Network, LayoutGrid, TrendingUp,
  AlertTriangle, CheckCircle2, BookOpen, Upload,
  ChevronDown, Check, FolderOpen,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { graphAPI, foldersAPI } from '../api/client';

// ── Force simulation with collision detection ─────────────────────────────────
const GW = 1000, GH = 680;

function runForce(nodes, edges, iterations = 500) {
  const REPEL = 22000, ATTRACT = 0.025, CENTER = 0.004, DAMPING = 0.86;

  // Degree-based radius: more connected = bigger node
  const degree = {};
  edges.forEach(e => {
    degree[e.source] = (degree[e.source] || 0) + 1;
    degree[e.target] = (degree[e.target] || 0) + 1;
  });

  nodes.forEach(n => {
    n.r = Math.round(Math.min(26, 14 + (degree[n.id] || 0) * 2.5));
    if (n.x == null) n.x = GW / 2 + (Math.random() - 0.5) * 700;
    if (n.y == null) n.y = GH / 2 + (Math.random() - 0.5) * 500;
    n.vx = 0; n.vy = 0;
  });

  const idxById = Object.fromEntries(nodes.map((n, i) => [n.id, i]));

  for (let iter = 0; iter < iterations; iter++) {
    const alpha = Math.max(0.1, 1 - iter / iterations);

    // Repulsion + collision between every pair
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[i].x - nodes[j].x || 0.1;
        let dy = nodes[i].y - nodes[j].y || 0.1;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const nx = dx / dist, ny = dy / dist;

        // Coulomb repulsion
        const rep = REPEL / (dist * dist + 1);
        nodes[i].vx += rep * nx; nodes[i].vy += rep * ny;
        nodes[j].vx -= rep * nx; nodes[j].vy -= rep * ny;

        // Hard collision push-apart
        const minD = (nodes[i].r + nodes[j].r) * 2.4;
        if (dist < minD) {
          const push = (minD - dist) * 0.6 * alpha;
          nodes[i].vx += push * nx; nodes[i].vy += push * ny;
          nodes[j].vx -= push * nx; nodes[j].vy -= push * ny;
        }
      }
    }

    // Spring attraction along edges (target length 140px)
    edges.forEach(e => {
      const si = idxById[e.source], ti = idxById[e.target];
      if (si == null || ti == null) return;
      const dx = nodes[ti].x - nodes[si].x, dy = nodes[ti].y - nodes[si].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const stretch = (dist - 140) / dist * ATTRACT;
      nodes[si].vx += stretch * dx; nodes[si].vy += stretch * dy;
      nodes[ti].vx -= stretch * dx; nodes[ti].vy -= stretch * dy;
    });

    nodes.forEach(n => {
      n.vx += (GW / 2 - n.x) * CENTER;
      n.vy += (GH / 2 - n.y) * CENTER;
      n.vx *= DAMPING; n.vy *= DAMPING;
      const pad = n.r + 28;
      n.x = Math.max(pad, Math.min(GW - pad, n.x + n.vx));
      n.y = Math.max(pad, Math.min(GH - pad - 12, n.y + n.vy));
    });
  }
  return nodes;
}

// ── Coverage helpers ─────────────────────────────────────────────────────────
const coverageLevel = s => s < 0.35 ? 'low' : s < 0.70 ? 'medium' : 'high';

const coverageConfig = {
  low:    { bar: 'bg-red-500',    text: 'text-red-600',    badge: 'bg-red-100 text-red-700 border-red-200',    label: 'Needs work' },
  medium: { bar: 'bg-yellow-500', text: 'text-yellow-600', badge: 'bg-yellow-100 text-yellow-700 border-yellow-200', label: 'In progress' },
  high:   { bar: 'bg-green-500',  text: 'text-green-600',  badge: 'bg-green-100 text-green-700 border-green-200',  label: 'Strong' },
};

// ── Cluster Card ─────────────────────────────────────────────────────────────
function ClusterCard({ cluster, onNoteClick }) {
  const pct = Math.round(cluster.coverage_score * 100);
  const level = coverageLevel(cluster.coverage_score);
  const cfg = coverageConfig[level];

  return (
    <div className="bg-card rounded-xl border border-border/60 shadow-sm hover:shadow-md transition-shadow duration-300 p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-sm leading-snug flex-1">{cluster.label}</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex-shrink-0 ${cfg.badge}`}>
          {cfg.label}
        </span>
      </div>
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span>Coverage</span>
          <span className={`font-bold tabular-nums ${cfg.text}`}>{pct}%</span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-700 ${cfg.bar}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="font-medium">{cluster.note_count} {cluster.note_count === 1 ? 'note' : 'notes'}</span>
        <span>·</span>
        <span>{cluster.total_words.toLocaleString()} words</span>
      </div>
      {cluster.member_titles.length > 0 && (
        <div className="space-y-0.5 pt-1 border-t border-border/50">
          {cluster.member_titles.map((title, i) => (
            <button key={i} onClick={() => onNoteClick(cluster.member_ids[i])}
              className="w-full text-left text-xs text-muted-foreground hover:text-foreground hover:bg-muted/60 rounded px-1.5 py-1 transition-colors truncate block">
              → {title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Progress Row ─────────────────────────────────────────────────────────────
function ProgressRow({ cluster, onNoteClick }) {
  const pct = Math.round(cluster.coverage_score * 100);
  const cfg = coverageConfig[coverageLevel(cluster.coverage_score)];

  return (
    <div className="py-4 border-b last:border-0">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm">{cluster.label}</span>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold tabular-nums ${cfg.text}`}>{pct}%</span>
          <span className={`text-xs px-2 py-0.5 rounded-full border ${cfg.badge}`}>{cfg.label}</span>
        </div>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden mb-2">
        <div className={`h-full rounded-full transition-all duration-700 ${cfg.bar}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{cluster.note_count} {cluster.note_count === 1 ? 'note' : 'notes'} · {cluster.total_words.toLocaleString()} words</span>
        <div className="flex gap-2">
          {cluster.member_ids.slice(0, 2).map((id, i) => (
            <button key={i} onClick={() => onNoteClick(id)} className="text-primary hover:underline max-w-[100px] truncate">
              {cluster.member_titles[i]}
            </button>
          ))}
          {cluster.member_ids.length > 2 && (
            <button onClick={() => onNoteClick(cluster.member_ids[0])} className="text-muted-foreground hover:text-foreground">
              +{cluster.member_ids.length - 2} more
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ProgressSection({ title, subtitle, icon: Icon, iconClass, clusters, onNoteClick }) {
  if (!clusters || clusters.length === 0) return null;
  return (
    <div className="bg-card rounded-xl border border-border/60 shadow-sm overflow-hidden mb-4">
      <div className="flex items-center gap-2 px-5 py-3 border-b bg-muted/30">
        <Icon className={`w-4 h-4 ${iconClass}`} />
        <span className="font-semibold text-sm">{title}</span>
        <span className="text-xs text-muted-foreground">— {subtitle}</span>
        <Badge variant="secondary" className="ml-auto text-xs">{clusters.length} topic{clusters.length !== 1 ? 's' : ''}</Badge>
      </div>
      <div className="px-5">
        {clusters.map((c, i) => <ProgressRow key={i} cluster={c} onNoteClick={onNoteClick} />)}
      </div>
    </div>
  );
}

// ── Graph Legend ─────────────────────────────────────────────────────────────
function GraphLegend({ stats }) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground border rounded-lg px-4 py-2.5 bg-card">
      <span className="flex items-center gap-1.5">
        <span className="w-3 h-3 rounded-full bg-cyan-400 inline-block" />
        Concept (1 note)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-3 h-3 rounded-full bg-blue-500 inline-block" />
        Concept (2 notes)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-3 h-3 rounded-full bg-violet-600 inline-block" />
        Concept (3+ notes)
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="20" height="4"><line x1="0" y1="2" x2="20" y2="2" stroke="#64748b" strokeWidth="2" /></svg>
        Co-occurs in note
      </span>
      <span className="ml-auto font-medium">
        {stats?.total_nodes ?? 0} concepts · {stats?.total_edges ?? 0} connections
      </span>
    </div>
  );
}

// ── Folder selector dropdown ─────────────────────────────────────────────────
function FolderSelector({ folders, selectedFolder, onChange }) {
  const selected = folders.find(f => f.id === selectedFolder);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <FolderOpen className="w-3.5 h-3.5" />
          <span className="max-w-[120px] truncate">{selected?.name ?? 'All folders'}</span>
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground ml-0.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuItem onClick={() => onChange(null)} className="gap-2">
          {!selectedFolder && <Check className="w-3.5 h-3.5 text-primary" />}
          <span className={!selectedFolder ? '' : 'ml-[22px]'}>All folders</span>
        </DropdownMenuItem>
        {folders.length > 0 && <DropdownMenuSeparator />}
        {folders.map(f => (
          <DropdownMenuItem key={f.id} onClick={() => onChange(f.id)} className="gap-2">
            {selectedFolder === f.id && <Check className="w-3.5 h-3.5 text-primary" />}
            <div className={`flex items-center gap-1.5 ${selectedFolder === f.id ? '' : 'ml-[22px]'}`}>
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: f.color }} />
              <span className="truncate">{f.name}</span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ── Shared empty state ───────────────────────────────────────────────────────
function EmptyState({ icon: Icon, title, subtitle, onUpload }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-muted-foreground border border-dashed rounded-2xl">
      <div className="inline-flex p-4 rounded-2xl bg-muted">
        <Icon className="w-10 h-10 text-muted-foreground" />
      </div>
      <div className="text-center">
        <p className="text-base font-medium text-foreground">{title}</p>
        <p className="text-sm mt-1">{subtitle}</p>
      </div>
      <Button size="sm" onClick={onUpload}>
        <Upload className="w-4 h-4 mr-2" />
        Upload Notes
      </Button>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export const Graph = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('graph');
  const [selectedFolder, setSelectedFolder] = useState(null);

  const svgRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [layoutNodes, setLayoutNodes] = useState([]);
  const [layoutEdges, setLayoutEdges] = useState([]);

  const { data: folders = [] } = useQuery({
    queryKey: ['folders'],
    queryFn: () => foldersAPI.getFolders(),
  });

  const graphQuery = useQuery({
    queryKey: ['knowledge-graph', selectedFolder],
    queryFn: () => graphAPI.getGraph(selectedFolder),
    staleTime: 0,
    refetchOnWindowFocus: false,
  });

  const clusterQuery = useQuery({
    queryKey: ['topic-clusters', selectedFolder],
    queryFn: () => graphAPI.getClusters(selectedFolder),
    staleTime: 0,
    refetchOnWindowFocus: false,
    enabled: activeTab === 'clusters',
  });

  const progressQuery = useQuery({
    queryKey: ['study-progress', selectedFolder],
    queryFn: () => graphAPI.getProgress(selectedFolder),
    staleTime: 0,
    refetchOnWindowFocus: false,
    enabled: activeTab === 'progress',
  });

  // Reset layout when graph data or folder changes
  useEffect(() => {
    if (!graphQuery.data) return;
    const { nodes = [], edges = [] } = graphQuery.data;
    if (nodes.length === 0) { setLayoutNodes([]); setLayoutEdges([]); return; }
    setLayoutNodes(runForce(nodes.map(n => ({ ...n })), edges));
    setLayoutEdges(edges);
  }, [graphQuery.data]);

  // Reset view when folder changes
  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [selectedFolder]);

  const onMouseDown = useCallback((e, type, nodeId) => {
    e.preventDefault();
    if (type === 'node') {
      setDragging({ type: 'node', nodeId, startX: e.clientX, startY: e.clientY });
    } else {
      setDragging({ type: 'pan', startX: e.clientX, startY: e.clientY, origX: pan.x, origY: pan.y });
    }
  }, [pan]);

  const onMouseMove = useCallback((e) => {
    if (!dragging) return;
    const dx = e.clientX - dragging.startX, dy = e.clientY - dragging.startY;
    if (dragging.type === 'pan') {
      setPan({ x: dragging.origX + dx, y: dragging.origY + dy });
    } else {
      setLayoutNodes(prev => prev.map(n =>
        n.id === dragging.nodeId ? { ...n, x: n.x + dx / zoom, y: n.y + dy / zoom } : n
      ));
      setDragging(d => ({ ...d, startX: e.clientX, startY: e.clientY }));
    }
  }, [dragging, zoom]);

  const onMouseUp = useCallback(() => setDragging(null), []);
  const onWheel = useCallback((e) => {
    e.preventDefault();
    setZoom(z => Math.max(0.3, Math.min(3, z * (e.deltaY < 0 ? 1.1 : 0.9))));
  }, []);
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const handleNodeClick = (node) => {
    if (node.type === 'note') navigate(`/note/${node.id.replace('note_', '')}`);
    else if (node.type === 'recording') navigate('/voice');
    // concept nodes: no navigation (they represent topics, not documents)
  };

  const handleFolderChange = (folderId) => {
    setSelectedFolder(folderId);
    // Trigger refetch for whichever tab is active
    if (activeTab === 'clusters') clusterQuery.refetch();
    if (activeTab === 'progress') progressQuery.refetch();
  };

  const handleRefresh = () => {
    if (activeTab === 'graph')    graphQuery.refetch();
    if (activeTab === 'clusters') clusterQuery.refetch();
    if (activeTab === 'progress') progressQuery.refetch();
  };

  const isRefetching =
    activeTab === 'graph' ? graphQuery.isRefetching :
    activeTab === 'clusters' ? clusterQuery.isRefetching :
    progressQuery.isRefetching;

  const gapCount = progressQuery.data?.gaps?.length ?? 0;
  const nodeById = Object.fromEntries(layoutNodes.map(n => [n.id, n]));
  const nodeColor = (n) => {
    if (n.type === 'concept') {
      const c = n.note_count || 1;
      if (c >= 3) return '#7c3aed';   // violet — many notes
      if (c >= 2) return '#3b82f6';   // blue — a few notes
      return '#06b6d4';               // cyan — single note
    }
    return n.type === 'recording' ? '#8b5cf6' : '#3b82f6';
  };
  const nodeStroke = (n) => {
    if (n.type === 'concept') {
      const c = n.note_count || 1;
      if (c >= 3) return '#5b21b6';
      if (c >= 2) return '#1d4ed8';
      return '#0891b2';
    }
    return n.type === 'recording' ? '#6d28d9' : '#1d4ed8';
  };
  const edgeColor = t => t === 'linked' ? '#a78bfa' : '#64748b';

  const selectedFolderObj = folders.find(f => f.id === selectedFolder);

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        {/* Glassmorphism header */}
        <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
          <div className="container flex h-16 items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => navigate('/library')} data-testid="back-library-btn">
              <ArrowLeft className="w-4 h-4 mr-2" />Library
            </Button>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold">Knowledge</h1>
              {selectedFolderObj && (
                <Badge variant="secondary" className="gap-1 text-xs font-normal">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: selectedFolderObj.color }} />
                  {selectedFolderObj.name}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <FolderSelector folders={folders} selectedFolder={selectedFolder} onChange={handleFolderChange} />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isRefetching}>
                    <RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Refresh</TooltipContent>
              </Tooltip>
            </div>
          </div>
        </header>

        <div className="container py-5">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="h-10 mb-5">
              <TabsTrigger value="graph" className="gap-2 text-sm">
                <Network className="w-4 h-4" />
                Knowledge Graph
              </TabsTrigger>
              <TabsTrigger value="clusters" className="gap-2 text-sm">
                <LayoutGrid className="w-4 h-4" />
                Topic Clusters
              </TabsTrigger>
              <TabsTrigger value="progress" className="gap-2 text-sm">
                <TrendingUp className="w-4 h-4" />
                Study Progress
                {gapCount > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full leading-none font-bold">
                    {gapCount}
                  </span>
                )}
              </TabsTrigger>
            </TabsList>

            {/* ── Knowledge Graph tab ── */}
            <TabsContent value="graph" className="space-y-3">
              {graphQuery.data && <GraphLegend stats={graphQuery.data.stats} />}

              <div className="flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="outline" onClick={() => setZoom(z => Math.min(3, z * 1.2))}>
                      <ZoomIn className="w-4 h-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Zoom in</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="outline" onClick={() => setZoom(z => Math.max(0.3, z / 1.2))}>
                      <ZoomOut className="w-4 h-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Zoom out</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="outline" onClick={resetView}>
                      <Maximize2 className="w-4 h-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Reset view</TooltipContent>
                </Tooltip>
                <span className="text-xs text-muted-foreground ml-1">
                  {Math.round(zoom * 100)}% · drag to pan · scroll to zoom · click node to open
                </span>
              </div>

              <div
                className="border rounded-xl overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 select-none shadow-inner"
                style={{ height: 620 }}
              >
                {graphQuery.isLoading ? (
                  <div className="flex flex-col items-center justify-center h-full gap-4">
                    <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-400 rounded-full animate-spin" />
                    <p className="text-sm text-slate-400">Building knowledge graph…</p>
                  </div>
                ) : layoutNodes.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-400">
                    <Network className="w-12 h-12 opacity-30" />
                    <div className="text-center">
                      <p className="text-sm font-medium text-white">
                        {selectedFolder ? 'No notes in this folder' : 'No notes yet'}
                      </p>
                      <p className="text-xs mt-1">
                        {selectedFolder ? 'Switch folders or upload notes here' : 'Upload notes to see how they connect'}
                      </p>
                    </div>
                    <Button size="sm" onClick={() => navigate('/upload')}>
                      <Upload className="w-4 h-4 mr-2" />
                      Upload Notes
                    </Button>
                  </div>
                ) : (
                  <svg
                    ref={svgRef}
                    width="100%" height="100%"
                    viewBox={`0 0 ${GW} ${GH}`}
                    onMouseDown={e => onMouseDown(e, 'pan')}
                    onMouseMove={onMouseMove}
                    onMouseUp={onMouseUp}
                    onMouseLeave={onMouseUp}
                    onWheel={onWheel}
                    style={{ cursor: dragging?.type === 'pan' ? 'grabbing' : 'grab' }}
                  >
                    <defs>
                      <filter id="node-glow" x="-40%" y="-40%" width="180%" height="180%">
                        <feGaussianBlur stdDeviation="3" result="blur" />
                        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                      </filter>
                      <filter id="label-shadow" x="-10%" y="-20%" width="120%" height="140%">
                        <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodOpacity="0.25" />
                      </filter>
                    </defs>

                    <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
                      {/* Edges — drawn first so they appear under nodes */}
                      {layoutEdges.map((e, i) => {
                        const s = nodeById[e.source], t = nodeById[e.target];
                        if (!s || !t) return null;
                        const isVoice = e.type === 'linked';
                        return (
                          <line key={i}
                            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                            stroke={edgeColor(e.type)}
                            strokeWidth={Math.max(1.2, (e.weight || 0.5) * 3.5)}
                            strokeOpacity={isVoice ? 0.65 : 0.5}
                            strokeDasharray={isVoice ? '6,4' : undefined}
                          />
                        );
                      })}

                      {/* Nodes */}
                      {layoutNodes.map(n => {
                        const r = n.r || 16;
                        const isHovered = hoveredNode === n.id;
                        const color = nodeColor(n);
                        const stroke = nodeStroke(n);
                        // Label: truncate to ~18 chars for below-node display
                        const label = n.title.length > 18 ? n.title.slice(0, 17) + '…' : n.title;
                        const labelW = Math.min(160, label.length * 7.2 + 16);

                        return (
                          <g key={n.id}
                            style={{ cursor: 'pointer' }}
                            onMouseDown={ev => { ev.stopPropagation(); onMouseDown(ev, 'node', n.id); }}
                            onMouseEnter={() => setHoveredNode(n.id)}
                            onMouseLeave={() => setHoveredNode(null)}
                            onClick={() => handleNodeClick(n)}
                          >
                            {/* Halo ring on hover */}
                            {isHovered && (
                              <circle cx={n.x} cy={n.y} r={r + 9}
                                fill={color} fillOpacity={0.15}
                                stroke={color} strokeOpacity={0.3} strokeWidth={1}
                              />
                            )}

                            {/* Main circle */}
                            <circle
                              cx={n.x} cy={n.y}
                              r={isHovered ? r + 3 : r}
                              fill={color}
                              fillOpacity={isHovered ? 1 : 0.9}
                              stroke={stroke}
                              strokeWidth={isHovered ? 2.5 : 1.8}
                              filter={isHovered ? 'url(#node-glow)' : undefined}
                            />

                            {/* Initials inside the circle (always visible) */}
                            <text
                              x={n.x} y={n.y}
                              dy="0.38em"
                              textAnchor="middle"
                              fontSize={r > 20 ? 12 : 10}
                              fill="white"
                              fontWeight="700"
                              pointerEvents="none"
                              fontFamily="system-ui, sans-serif"
                            >
                              {n.title.slice(0, 2).toUpperCase()}
                            </text>

                            {/* Label pill below the node */}
                            <g transform={`translate(${n.x},${n.y + r + 6})`} pointerEvents="none">
                              <rect
                                x={-labelW / 2} y={0}
                                width={labelW} height={17}
                                rx={8}
                                fill={isHovered ? color : 'rgba(15,23,42,0.78)'}
                                filter="url(#label-shadow)"
                              />
                              <text
                                x={0} y={12}
                                textAnchor="middle"
                                fontSize={11}
                                fill="white"
                                fontWeight={isHovered ? '600' : '400'}
                                fontFamily="system-ui, sans-serif"
                              >
                                {label}
                              </text>
                            </g>

                            {/* Full-title tooltip on hover (above the node) */}
                            {isHovered && (n.title.length > 18 || n.note_count > 0) && (
                              <g transform={`translate(${n.x},${n.y - r - 14})`} pointerEvents="none">
                                <rect
                                  x={-100} y={-16}
                                  width={200} height={20}
                                  rx={6}
                                  fill="rgba(2,8,23,0.9)"
                                  stroke="rgba(255,255,255,0.1)"
                                  strokeWidth={0.5}
                                />
                                <text
                                  x={0} y={-3}
                                  textAnchor="middle"
                                  fontSize={11}
                                  fill="white"
                                  fontWeight="500"
                                  fontFamily="system-ui, sans-serif"
                                >
                                  {n.title.length > 34 ? n.title.slice(0, 33) + '…' : n.title}
                                  {n.note_count > 0 ? ` · ${n.note_count} note${n.note_count !== 1 ? 's' : ''}` : ''}
                                </text>
                              </g>
                            )}
                          </g>
                        );
                      })}
                    </g>
                  </svg>
                )}
              </div>
            </TabsContent>

            {/* ── Topic Clusters tab ── */}
            <TabsContent value="clusters">
              {clusterQuery.isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="rounded-xl border bg-card p-4 space-y-3">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-2 w-full rounded-full" />
                      <Skeleton className="h-3 w-1/2" />
                    </div>
                  ))}
                </div>
              ) : !clusterQuery.data || clusterQuery.data.clusters?.length === 0 ? (
                <EmptyState
                  icon={LayoutGrid}
                  title={selectedFolder ? 'No indexed notes in this folder' : (clusterQuery.data?.total_notes === 0 ? 'No notes yet' : 'Notes not indexed')}
                  subtitle={selectedFolder ? 'Assign notes to this folder, then reindex via the AI sidebar' : 'Upload notes and reindex via the RAG sidebar'}
                  onUpload={() => navigate('/upload')}
                />
              ) : (
                <>
                  <div className="flex items-center gap-4 mb-4 text-sm text-muted-foreground">
                    <span>
                      {clusterQuery.data.k} cluster{clusterQuery.data.k !== 1 ? 's' : ''} · {clusterQuery.data.indexed_notes} note{clusterQuery.data.indexed_notes !== 1 ? 's' : ''}
                      {selectedFolderObj && ` in "${selectedFolderObj.name}"`}
                    </span>
                    {clusterQuery.data.clusters.filter(c => c.coverage_score < 0.35).length > 0 && (
                      <span className="flex items-center gap-1.5 text-red-600 font-medium">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        {clusterQuery.data.clusters.filter(c => c.coverage_score < 0.35).length} need{clusterQuery.data.clusters.filter(c => c.coverage_score < 0.35).length === 1 ? 's' : ''} attention
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {clusterQuery.data.clusters.map((cluster, i) => (
                      <ClusterCard key={i} cluster={cluster} onNoteClick={id => navigate(`/note/${id}`)} />
                    ))}
                  </div>
                </>
              )}
            </TabsContent>

            {/* ── Study Progress tab ── */}
            <TabsContent value="progress">
              {progressQuery.isLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-32 w-full rounded-xl" />
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="rounded-xl border bg-card p-5 space-y-2">
                      <Skeleton className="h-4 w-1/3" />
                      <Skeleton className="h-2 w-full rounded-full" />
                    </div>
                  ))}
                </div>
              ) : !progressQuery.data || progressQuery.data.total_topics === 0 ? (
                <EmptyState
                  icon={TrendingUp}
                  title={progressQuery.data?.needs_reindex ? 'Notes not indexed yet' : (selectedFolder ? 'No indexed notes in this folder' : 'No notes yet')}
                  subtitle={progressQuery.data?.needs_reindex
                    ? 'Open the AI sidebar → click Reindex, then refresh'
                    : selectedFolder
                      ? 'Assign notes to this folder, then reindex'
                      : 'Upload and save notes to track your study progress'}
                  onUpload={() => navigate('/upload')}
                />
              ) : (
                <>
                  {/* Overall card */}
                  <div className="bg-card rounded-xl border border-border/60 shadow-sm p-5 mb-5">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h2 className="text-base font-semibold">
                          Study Coverage
                          {selectedFolderObj && (
                            <span className="font-normal text-muted-foreground"> — {selectedFolderObj.name}</span>
                          )}
                        </h2>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {progressQuery.data.total_notes} note{progressQuery.data.total_notes !== 1 ? 's' : ''} · {progressQuery.data.total_topics} topic{progressQuery.data.total_topics !== 1 ? 's' : ''} · {progressQuery.data.total_words.toLocaleString()} words
                        </p>
                      </div>
                      <div className="text-right">
                        <span className={`text-4xl font-bold tabular-nums ${coverageConfig[coverageLevel(progressQuery.data.overall_coverage)].text}`}>
                          {Math.round(progressQuery.data.overall_coverage * 100)}%
                        </span>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {coverageConfig[coverageLevel(progressQuery.data.overall_coverage)].label}
                        </p>
                      </div>
                    </div>
                    <div className="h-3 bg-muted rounded-full overflow-hidden mb-3">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${coverageConfig[coverageLevel(progressQuery.data.overall_coverage)].bar}`}
                        style={{ width: `${progressQuery.data.overall_coverage * 100}%` }}
                      />
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm">
                      {progressQuery.data.gaps.length > 0 && (
                        <span className="flex items-center gap-1.5 text-red-600 font-medium">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {progressQuery.data.gaps.length} gap{progressQuery.data.gaps.length !== 1 ? 's' : ''}
                        </span>
                      )}
                      {progressQuery.data.moderate.length > 0 && (
                        <span className="text-yellow-600 font-medium">{progressQuery.data.moderate.length} moderate</span>
                      )}
                      {progressQuery.data.strong.length > 0 && (
                        <span className="flex items-center gap-1.5 text-green-600 font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          {progressQuery.data.strong.length} strong
                        </span>
                      )}
                    </div>
                  </div>

                  <ProgressSection title="Knowledge Gaps" subtitle="study these first" icon={AlertTriangle} iconClass="text-red-500" clusters={progressQuery.data.gaps} onNoteClick={id => navigate(`/note/${id}`)} />
                  <ProgressSection title="Moderate Coverage" subtitle="keep adding notes" icon={BookOpen} iconClass="text-yellow-500" clusters={progressQuery.data.moderate} onNoteClick={id => navigate(`/note/${id}`)} />
                  <ProgressSection title="Well Covered" subtitle="great work" icon={CheckCircle2} iconClass="text-green-500" clusters={progressQuery.data.strong} onNoteClick={id => navigate(`/note/${id}`)} />
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </TooltipProvider>
  );
};

export default Graph;

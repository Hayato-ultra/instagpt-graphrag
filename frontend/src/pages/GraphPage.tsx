import React, { useCallback, useMemo, useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Plus, Loader2, X } from 'lucide-react'
import { api } from '../services/api'
import { useAppStore } from '../store'
import NodeStickyNote from '../components/NodeStickyNote'

const nodeColors: Record<string, string> = {
  video: '#58a6ff', topic: '#a371f7', subtopic: '#c297ff',
  tool: '#f0883e', concept: '#3fb950', workflow: '#d2a8ff',
  tip: '#f778ba', bugfix: '#f85149', platform: '#79c0ff',
  library: '#8b949e', web_app: '#7ee787', framework: '#d2a8ff',
  entity: '#58a6ff', creative_software: '#d2a8ff',
}
const edgeColor = '#58a6ff'

function GraphNode({ data }: { data: { label: string; type: string; isMaster?: boolean } }) {
  if (data.isMaster) {
    return (
      <div className="w-16 h-16 rounded-full border-2 border-dashed flex items-center justify-center"
        style={{ borderColor: '#8b949e', backgroundColor: 'rgba(139,148,158,0.08)' }}>
        <span className="text-[10px] text-outline uppercase tracking-wider">{data.type}</span>
      </div>
    )
  }
  const color = nodeColors[data.type] || '#8b949e'
  return (
    <div className="px-3 py-1.5 rounded-lg border-2 text-xs font-medium"
      style={{ borderColor: color, backgroundColor: `${color}20`, color, minWidth: 80, textAlign: 'center' }}>
      <div>{data.label}</div>
    </div>
  )
}
const nodeTypes = { custom: GraphNode }

function AddNodePanel({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [type, setType] = useState('entity')
  const [description, setDescription] = useState('')
  const [topic, setTopic] = useState('')

  const { data: graphData } = useQuery({ queryKey: ['graph'], queryFn: api.getGraph })
  const existingTypes = useMemo(() => {
    if (!graphData) return []
    return [...new Set(graphData.nodes.map((n) => n.type || 'entity'))]
  }, [graphData])

  const createMutation = useMutation({
    mutationFn: () => api.createNode({
      name, type, description, topic,
      content_type: 'custom',
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['graph'] })
      onClose()
    },
  })

  return (
    <div className="absolute top-4 right-4 z-40 w-80 rounded-xl border border-outline-variant bg-surface/95 backdrop-blur-md shadow-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-on-surface">Add Custom Node</h3>
        <button onClick={onClose} className="w-6 h-6 rounded-full flex items-center justify-center hover:bg-white/10">
          <X size={12} className="text-on-surface-variant" />
        </button>
      </div>
      <div>
        <label className="text-[11px] text-outline uppercase tracking-wider mb-1 block">Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Node name"
          className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary" />
      </div>
      <div>
        <label className="text-[11px] text-outline uppercase tracking-wider mb-1 block">Cluster (type)</label>
        <div className="flex gap-1.5 flex-wrap mb-1.5">
          {existingTypes.map((t) => (
            <button key={t} onClick={() => setType(t)}
              className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${type === t ? 'text-white' : 'text-on-surface-variant border-outline-variant hover:border-primary/50'}`}
              style={type === t ? { backgroundColor: nodeColors[t] || '#8b949e', borderColor: nodeColors[t] || '#8b949e' } : {}}>
              {t}
            </button>
          ))}
        </div>
        <input value={type} onChange={(e) => setType(e.target.value)} placeholder="or type a new cluster name"
          className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary" />
      </div>
      <div>
        <label className="text-[11px] text-outline uppercase tracking-wider mb-1 block">Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
          className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary resize-none" />
      </div>
      <div>
        <label className="text-[11px] text-outline uppercase tracking-wider mb-1 block">Topic</label>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Optional"
          className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary" />
      </div>
      <button onClick={() => createMutation.mutate()} disabled={!name.trim() || createMutation.isPending}
        className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium text-white bg-primary hover:bg-primary/80 disabled:opacity-40 transition-colors">
        {createMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
        {createMutation.isError ? 'Failed - Retry' : 'Create Node'}
      </button>
    </div>
  )
}

function GraphInner() {
  const { setSelectedNode, setGraphData } = useAppStore()
  const { fitView } = useReactFlow()
  const [layoutKey, setLayoutKey] = useState(0)
  const [stickyNotes, setStickyNotes] = useState<Array<{ node: any }>>([])
  const [showAddNode, setShowAddNode] = useState(false)

  const { data: graphData } = useQuery({ queryKey: ['graph'], queryFn: api.getGraph })

  const [nodes, setNodes, onNodesChange] = React.useState<Node[]>([])
  const [edges, setEdges, onEdgesChange] = React.useState<Edge[]>([])

  useEffect(() => {
    if (!graphData) return

    setGraphData(graphData.nodes, graphData.edges)

    // Filter out nodes with no meaningful content
    const meaningful = graphData.nodes.filter((n) => {
      const p = n.properties || {}
      return n.description || p.summary || p.source_url || p.key_points
    })
    const meaningfulIds = new Set(meaningful.map((n) => n.id))

    const groups: Record<string, typeof meaningful> = {}
    for (const node of meaningful) {
      const t = node.type || 'entity'
      if (!groups[t]) groups[t] = []
      groups[t].push(node)
    }

    const groupKeys = Object.keys(groups)
    const cols = Math.ceil(Math.sqrt(groupKeys.length))
    const clusterSpacing = 500

    const flowNodes: Node[] = []
    const flowEdges: Edge[] = []

    groupKeys.forEach((type, gi) => {
      const row = Math.floor(gi / cols)
      const col = gi % cols
      const cx = col * clusterSpacing
      const cy = row * clusterSpacing
      const members = groups[type]

      flowNodes.push({
        id: `master-${type}`,
        type: 'custom',
        position: { x: cx, y: cy },
        data: { label: '', type, isMaster: true },
      })

      const subRadius = Math.max(120, members.length * 25)
      members.forEach((node, mi) => {
        const angle = (2 * Math.PI * mi) / members.length - Math.PI / 2
        flowNodes.push({
          id: node.id,
          type: 'custom',
          position: { x: cx + Math.cos(angle) * subRadius, y: cy + Math.sin(angle) * subRadius },
          data: { label: node.label, type: node.type },
        })
        flowEdges.push({
          id: `edge-master-${type}--${node.id}`,
          source: `master-${type}`,
          target: node.id,
          style: { stroke: nodeColors[type] || '#8b949e', strokeWidth: 1, opacity: 0.4 },
        })
      })
    })

    for (const edge of graphData.edges) {
      if (!meaningfulIds.has(edge.source) || !meaningfulIds.has(edge.target)) continue
      flowEdges.push({
        id: `edge-${edge.source}--${edge.target}`,
        source: edge.source,
        target: edge.target,
        style: { stroke: edgeColor, strokeWidth: 1.5, opacity: 0.6 },
        type: 'default',
      })
    }

    setNodes(flowNodes)
    setEdges(flowEdges)
    setTimeout(() => fitView({ padding: 0.3, duration: 500 }), 100)
  }, [graphData, layoutKey])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if ((node.data as any)?.isMaster) return
      const graphNode = graphData?.nodes.find((n) => n.id === node.id)
      if (!graphNode) return
      setStickyNotes((prev) => {
        if (prev.some((s) => s.node.id === graphNode.id)) return prev
        return [...prev, { node: graphNode }]
      })
    },
    [graphData]
  )

  const removeSticky = useCallback((nodeId: string) => {
    setStickyNotes((prev) => prev.filter((s) => s.node.id !== nodeId))
  }, [])

  const onPaneClick = useCallback(() => {
    setStickyNotes([])
    setSelectedNode(null as any)
  }, [setSelectedNode])

  const stats = useMemo(() => {
    if (!graphData) return { nodes: 0, edges: 0, clusters: 0 }
    const meaningful = graphData.nodes.filter((n) => {
      const p = n.properties || {}
      return n.description || p.summary || p.source_url || p.key_points
    })
    const meaningfulIds = new Set(meaningful.map((n) => n.id))
    const edgeCount = graphData.edges.filter((e) => meaningfulIds.has(e.source) && meaningfulIds.has(e.target)).length
    const types = new Set(meaningful.map((n) => n.type || 'entity'))
    return { nodes: meaningful.length, edges: edgeCount, clusters: types.size }
  }, [graphData])

  return (
    <div className="flex h-full">
      <div className="flex-1 relative">
        <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
          <div className="rounded-lg px-3 py-2 text-sm bg-black/60 backdrop-blur-md text-gray-300">
            {stats.clusters} clusters · {stats.nodes} nodes · {stats.edges} edges
          </div>
          <button onClick={() => setShowAddNode(true)}
            className="rounded-lg px-3 py-2 text-sm bg-primary/80 hover:bg-primary backdrop-blur-md text-white flex items-center gap-1.5 transition-colors">
            <Plus size={14} /> Add Node
          </button>
        </div>

        <ReactFlow
          nodes={nodes} edges={edges}
          onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick} onPaneClick={onPaneClick}
          nodeTypes={nodeTypes} fitView
          defaultEdgeOptions={{ type: 'default', style: { stroke: edgeColor, strokeWidth: 1.5 } }}
        >
          <Background color="#2D2D2D" />
          <Controls />
          <MiniMap nodeColor={(n) => nodeColors[n.data?.type as string] || '#8b949e'} />
        </ReactFlow>

        {stickyNotes.map((sn) => (
          <NodeStickyNote key={sn.node.id} node={sn.node} allNodes={graphData?.nodes.filter((n) => { const p = n.properties || {}; return n.description || p.summary || p.source_url || p.key_points }) || []} onClose={() => removeSticky(sn.node.id)} />
        ))}

        {showAddNode && <AddNodePanel onClose={() => { setShowAddNode(false); setLayoutKey((k) => k + 1) }} />}
      </div>
    </div>
  )
}

export default function GraphPage() {
  return (
    <ReactFlowProvider>
      <GraphInner />
    </ReactFlowProvider>
  )
}

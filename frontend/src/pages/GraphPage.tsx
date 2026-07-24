import { useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api } from '../services/api'
import { useAppStore } from '../store'
import NodeSidebar from '../components/NodeSidebar'
import { useEffect } from 'react'

const nodeColors: Record<string, string> = {
  video: '#58a6ff',
  topic: '#a371f7',
  subtopic: '#c297ff',
  tool: '#f0883e',
  concept: '#3fb950',
  workflow: '#d2a8ff',
  tip: '#f778ba',
  bugfix: '#f85149',
}

function GraphNode({ data }: { data: { label: string; type: string } }) {
  const color = nodeColors[data.type] || '#8b949e'
  return (
    <div
      className="px-4 py-2 rounded-lg border-2 text-sm font-medium shadow-lg"
      style={{
        borderColor: color,
        backgroundColor: `${color}15`,
        color: color,
      }}
    >
      <div className="text-xs opacity-60 mb-0.5">{data.type}</div>
      {data.label}
    </div>
  )
}

const nodeTypes = { custom: GraphNode }

export default function GraphPage() {
  const { selectedNode, setSelectedNode, setGraphData } = useAppStore()

  const { data: graphData } = useQuery({
    queryKey: ['graph'],
    queryFn: api.getGraph,
  })

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    if (!graphData) return

    setGraphData(graphData.nodes, graphData.edges)

    const flowNodes: Node[] = graphData.nodes.map((node, i) => ({
      id: node.id,
      type: 'custom',
      position: {
        x: Math.cos(2 * Math.PI * i / graphData.nodes.length) * 300,
        y: Math.sin(2 * Math.PI * i / graphData.nodes.length) * 300,
      },
      data: { label: node.label, type: node.type },
    }))

    const flowEdges: Edge[] = graphData.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.type,
      animated: edge.confidence < 0.8,
      style: { stroke: '#30363d' },
      labelStyle: { fill: '#8b949e', fontSize: 10 },
    }))

    setNodes(flowNodes)
    setEdges(flowEdges)
  }, [graphData])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const graphNode = graphData?.nodes.find((n) => n.id === node.id)
      if (graphNode) {
        setSelectedNode(graphNode)
      }
    }
  , [graphData, setSelectedNode])

  const stats = useMemo(() => {
    if (!graphData) return { nodes: 0, edges: 0 }
    return {
      nodes: graphData.nodes.length,
      edges: graphData.edges.length,
    }
  }, [graphData])

  return (
    <div className="flex h-full">
      <div className="flex-1 relative">
        <div className="absolute top-4 left-4 z-10 bg-surface/80 backdrop-blur rounded-lg px-3 py-2 text-sm border border-border">
          {stats.nodes} nodes · {stats.edges} edges
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          className="bg-bg"
        >
          <Background color="#30363d" />
          <Controls className="bg-surface border border-border" />
          <MiniMap
            nodeColor={(n) => nodeColors[n.data?.type as string] || '#8b949e'}
            className="bg-surface border border-border"
          />
        </ReactFlow>
      </div>
      {selectedNode && <NodeSidebar />}
    </div>
  )
}

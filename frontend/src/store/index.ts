import { create } from 'zustand'
import type { GraphNode, GraphEdge } from '../types'

interface AppState {
  selectedNode: GraphNode | null
  graphNodes: GraphNode[]
  graphEdges: GraphEdge[]
  sidebarOpen: boolean
  setSelectedNode: (node: GraphNode | null) => void
  setGraphData: (nodes: GraphNode[], edges: GraphEdge[]) => void
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>((set) => ({
  selectedNode: null,
  graphNodes: [],
  graphEdges: [],
  sidebarOpen: true,
  setSelectedNode: (node) => set({ selectedNode: node }),
  setGraphData: (nodes, edges) => set({ graphNodes: nodes, graphEdges: edges }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))

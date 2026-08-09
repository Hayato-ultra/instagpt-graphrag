export interface Video {
  id: string
  url: string
  title: string
  summary: string
  entities_count: number
  created_at: string
}

export interface VideoDetail extends Video {
  transcript: string
}

export interface AnalysisStatus {
  analysis_id: string
  status: string
  stage: string
  video_id?: string
}

export interface GraphNode {
  id: string
  type: string
  label: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  sourceType: string
  targetType: string
  confidence: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface NodeDetail {
  id: string
  type: string
  name: string
  description: string
  properties: Record<string, unknown>
  related_nodes: Array<{
    id: string
    type: string
    relation: string
  }>
}

export interface NotebookEntry {
  id: string
  video_id: string
  title: string
  summary: string
  ai_notes: string
  links: string
  tags: string
  created_at: string
}

export interface SearchResult {
  type: string
  id: string
  name: string
  description: string
}

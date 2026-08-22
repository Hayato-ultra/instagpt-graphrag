const API_BASE = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  analyzeVideo: (url: string) =>
    fetchJSON<{ analysis_id: string; status: string; stage: string; video_id?: string }>(
      '/video/analyze',
      { method: 'POST', body: JSON.stringify({ url }) }
    ),

  getAnalysisStatus: (id: string) =>
    fetchJSON<{ analysis_id: string; status: string; stage: string; video_id?: string }>(
      `/video/analysis/${id}`
    ),

  getVideo: (id: string) =>
    fetchJSON<{ id: string; youtube_id: string; url: string; title: string; channel: string; thumbnail: string; duration: number; summary: string; transcript: string; created_at: string }>(
      `/video/${id}`
    ),

  listVideos: () =>
    fetchJSON<Array<{ id: string; youtube_id: string; url: string; title: string; channel: string; thumbnail: string; duration: number; summary: string; created_at: string }>>(
      '/video/'
    ),

  getGraph: () =>
    fetchJSON<{ nodes: Array<{ id: string; type: string; label: string; properties: Record<string, unknown> }>; edges: Array<{ id: string; source: string; target: string; type: string; sourceType: string; targetType: string; confidence: number }> }>(
      '/graph'
    ),

  getVideoGraph: (videoId: string) =>
    fetchJSON<{ nodes: Array<{ id: string; type: string; label: string; properties: Record<string, unknown> }>; edges: Array<{ id: string; source: string; target: string; type: string; sourceType: string; targetType: string; confidence: number }> }>(
      `/graph/video/${videoId}`
    ),

  getNodeDetail: (type: string, id: string) =>
    fetchJSON<{ id: string; type: string; name: string; description: string; properties: Record<string, unknown>; related_nodes: Array<{ id: string; type: string; relation: string }> }>(
      `/graph/node/${type}/${id}`
    ),

  search: (query: string, filters?: string[]) =>
    fetchJSON<{ results: Array<{ type: string; id: string; name: string; description: string }>; total: number }>(
      '/search',
      { method: 'POST', body: JSON.stringify({ query, filters }) }
    ),

  listNotebook: () =>
    fetchJSON<{ entries: Array<{ id: string; video_id: string; title: string; summary: string; ai_notes: string; links: string; tags: string; created_at: string }>; total: number }>(
      '/notebook'
    ),

  getNotebookEntry: (id: string) =>
    fetchJSON<{ id: string; video_id: string; title: string; summary: string; ai_notes: string; links: string; tags: string; created_at: string }>(
      `/notebook/${id}`
    ),

  editNode: (nodeId: string, fields: Record<string, string>) =>
    fetchJSON<{ ok: boolean; node: Record<string, unknown> }>(
      `/graph/node/${encodeURIComponent(nodeId)}`,
      { method: 'PUT', body: JSON.stringify(fields) }
    ),

  mergeNodes: (sourceId: string, targetId: string, mergedName?: string, mergedDescription?: string) =>
    fetchJSON<{ ok: boolean; merged_into: string }>(
      '/graph/merge',
      { method: 'POST', body: JSON.stringify({ source_id: sourceId, target_id: targetId, merged_name: mergedName, merged_description: mergedDescription }) }
    ),

  createNode: (data: { name: string; type?: string; description?: string; summary?: string; topic?: string; sub_topic?: string; tags?: string; key_points?: string; content_type?: string; source_url?: string }) =>
    fetchJSON<{ ok: boolean; node: Record<string, unknown> }>(
      '/graph/node',
      { method: 'POST', body: JSON.stringify(data) }
    ),
}

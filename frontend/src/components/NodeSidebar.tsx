import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { useAppStore } from '../store'
import { X, ExternalLink, ArrowRight } from 'lucide-react'

const typeColors: Record<string, string> = {
  video: 'text-blue-400',
  topic: 'text-purple-400',
  subtopic: 'text-violet-300',
  tool: 'text-orange-400',
  concept: 'text-green-400',
  workflow: 'text-pink-400',
  tip: 'text-pink-300',
  bugfix: 'text-red-400',
}

export default function NodeSidebar() {
  const { selectedNode, setSelectedNode } = useAppStore()

  const { data: detail } = useQuery({
    queryKey: ['node', selectedNode?.type, selectedNode?.id],
    queryFn: () => api.getNodeDetail(selectedNode!.type, selectedNode!.id),
    enabled: !!selectedNode,
  })

  if (!selectedNode) return null

  return (
    <div className="w-96 bg-surface border-l border-border overflow-y-auto">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div>
          <span className={`text-xs font-medium ${typeColors[selectedNode.type] || 'text-muted'}`}>
            {selectedNode.type.toUpperCase()}
          </span>
          <h2 className="text-lg font-semibold mt-1">{selectedNode.label}</h2>
        </div>
        <button
          onClick={() => setSelectedNode(null)}
          className="text-muted hover:text-text p-1"
        >
          <X size={20} />
        </button>
      </div>

      {detail && (
        <div className="p-4">
          {detail.description && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-muted mb-2">Description</h3>
              <p className="text-sm">{detail.description}</p>
            </div>
          )}

          <div className="mb-4">
            <h3 className="text-sm font-medium text-muted mb-2">Properties</h3>
            <div className="space-y-2">
              {Object.entries(detail.properties).map(([key, value]) => {
                if (key === 'id' || key === 'created_at' || !value) return null
                return (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-muted">{key}</span>
                    <span className="text-right max-w-[200px] truncate">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {detail.related_nodes.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-muted mb-2">Related</h3>
              <div className="space-y-1">
                {detail.related_nodes.map((node, i) => (
                  <button
                    key={i}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-border/50 text-left"
                  >
                    <ArrowRight size={12} className="text-muted" />
                    <span className={`text-xs ${typeColors[node.type] || 'text-muted'}`}>
                      {node.type}
                    </span>
                    <span className="truncate flex-1">{node.relation}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

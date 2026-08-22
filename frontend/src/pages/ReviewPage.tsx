import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Star, CheckCircle, AlertTriangle, GitBranch, Lightbulb, Wrench, Layers } from 'lucide-react'

const typeIcons: Record<string, typeof Star> = {
  tool: Wrench,
  concept: Layers,
  topic: Lightbulb,
  subtopic: Lightbulb,
  entity: Star,
}

const typeColors: Record<string, string> = {
  tool: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
  concept: 'text-green-400 bg-green-400/10 border-green-400/20',
  topic: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
  subtopic: 'text-violet-300 bg-violet-400/10 border-violet-400/20',
  entity: 'text-teal-400 bg-teal-400/10 border-teal-400/20',
}

export default function ReviewPage() {
  const [activeTab, setActiveTab] = useState<'quality' | 'relationships'>('quality')

  const { data: graph, isLoading } = useQuery({
    queryKey: ['graph'],
    queryFn: api.getGraph,
  })

  const nodes = graph?.nodes || []
  const edges = graph?.edges || []

  const entities = nodes.filter((n) => n.type !== 'topic' && n.type !== 'subtopic')
  const entitiesWithDesc = entities.filter((e) => e.properties.description)
  const entitiesWithoutDesc = entities.filter((e) => !e.properties.description)

  const highConfEdges = edges.filter((e) => e.confidence >= 0.8)
  const lowConfEdges = edges.filter((e) => e.confidence < 0.5)

  return (
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">Review</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Review entity quality and relationship confidence across your knowledge graph.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-sm mb-xl">
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <CheckCircle size={16} className="text-green-400" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Described</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{entitiesWithDesc.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">
            / {entities.length} entities
          </span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <AlertTriangle size={16} className="text-yellow-400" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">No Description</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{entitiesWithoutDesc.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">need review</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <GitBranch size={16} className="text-primary" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">High Confidence</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{highConfEdges.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">edges</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <AlertTriangle size={16} className="text-orange-400" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Low Confidence</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{lowConfEdges.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">edges</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-xs mb-xl border-b border-outline-variant pb-2">
        <button
          onClick={() => setActiveTab('quality')}
          className={`px-md py-sm rounded-lg font-label-sm text-label-sm transition-colors ${
            activeTab === 'quality'
              ? 'bg-primary/10 text-primary border border-primary/30'
              : 'text-on-surface-variant hover:bg-surface-variant border border-transparent'
          }`}
        >
          Entity Quality
        </button>
        <button
          onClick={() => setActiveTab('relationships')}
          className={`px-md py-sm rounded-lg font-label-sm text-label-sm transition-colors ${
            activeTab === 'relationships'
              ? 'bg-primary/10 text-primary border border-primary/30'
              : 'text-on-surface-variant hover:bg-surface-variant border border-transparent'
          }`}
        >
          Relationship Confidence
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 rounded-full bg-primary/20 border-2 border-primary text-primary flex items-center justify-center mx-auto animate-pulse-ring">
            <span className="material-symbols-outlined animate-spin" style={{ animationDuration: '3s' }}>sync</span>
          </div>
          <p className="text-on-surface-variant mt-4 font-body-md">Loading review data...</p>
        </div>
      ) : activeTab === 'quality' ? (
        <div>
          <h2 className="font-h2 text-h2 text-on-surface mb-md">Entities Without Descriptions</h2>
          {entitiesWithoutDesc.length === 0 ? (
            <div className="layer-1 rounded-xl p-lg text-center">
              <CheckCircle size={48} className="mx-auto text-green-400 mb-4" />
              <p className="text-on-surface text-lg">All entities have descriptions</p>
              <p className="text-on-surface-variant text-sm mt-2">Great job maintaining your knowledge graph quality!</p>
            </div>
          ) : (
            <div className="grid gap-sm">
              {entitiesWithoutDesc.map((entity) => {
                const Icon = typeIcons[entity.type] || Star
                const colorClass = typeColors[entity.type] || typeColors.entity
                return (
                  <div
                    key={entity.id}
                    className="bg-surface-container-lowest border border-yellow-400/20 rounded-lg p-md flex items-center gap-md"
                  >
                    <div className={`p-2 rounded-lg border shrink-0 ${colorClass}`}>
                      <Icon size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-body-md text-body-md text-on-surface font-medium truncate">{entity.label}</h3>
                        <span className="font-mono text-mono text-outline text-[11px] px-2 py-0.5 bg-surface-variant rounded border border-outline-variant">
                          {entity.type}
                        </span>
                      </div>
                      <p className="text-sm text-yellow-400/80 mt-1 flex items-center gap-1">
                        <AlertTriangle size={12} />
                        Missing description — entity needs enrichment
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div>
          <h2 className="font-h2 text-h2 text-on-surface mb-md">Low Confidence Relationships</h2>
          {lowConfEdges.length === 0 ? (
            <div className="layer-1 rounded-xl p-lg text-center">
              <CheckCircle size={48} className="mx-auto text-green-400 mb-4" />
              <p className="text-on-surface text-lg">All relationships have high confidence</p>
              <p className="text-on-surface-variant text-sm mt-2">Your graph relationships are well-established.</p>
            </div>
          ) : (
            <div className="grid gap-sm">
              {lowConfEdges.map((edge) => (
                <div
                  key={edge.id}
                  className="bg-surface-container-lowest border border-orange-400/20 rounded-lg p-md"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-sm">
                      <span className="font-body-md text-body-md text-on-surface font-medium">{edge.source}</span>
                      <span className="material-symbols-outlined text-outline text-[16px]">arrow_forward</span>
                      <span className="font-body-md text-body-md text-on-surface font-medium">{edge.target}</span>
                    </div>
                    <div className="flex items-center gap-sm">
                      <span className="font-mono text-mono text-xs px-2 py-0.5 bg-surface-variant rounded border border-outline-variant text-outline">
                        {edge.type}
                      </span>
                      <span className="font-mono text-mono text-xs px-2 py-0.5 bg-orange-400/10 rounded border border-orange-400/20 text-orange-400">
                        {(edge.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-surface-variant h-1.5 rounded-full overflow-hidden mt-3">
                    <div
                      className="h-full rounded-full transition-all duration-500 bg-orange-400"
                      style={{ width: `${edge.confidence * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

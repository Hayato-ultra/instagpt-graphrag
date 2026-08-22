import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Lightbulb, Wrench, Layers, Workflow, Video, Tag, GitBranch, Search } from 'lucide-react'

const typeConfig: Record<string, { icon: typeof Video; color: string; label: string }> = {
  tool: { icon: Wrench, color: 'text-orange-400 bg-orange-400/10 border-orange-400/20', label: 'Tool' },
  concept: { icon: Layers, color: 'text-green-400 bg-green-400/10 border-green-400/20', label: 'Concept' },
  topic: { icon: Lightbulb, color: 'text-purple-400 bg-purple-400/10 border-purple-400/20', label: 'Topic' },
  subtopic: { icon: Lightbulb, color: 'text-violet-300 bg-violet-400/10 border-violet-400/20', label: 'Subtopic' },
  workflow: { icon: Workflow, color: 'text-pink-400 bg-pink-400/10 border-pink-400/20', label: 'Workflow' },
  video: { icon: Video, color: 'text-blue-400 bg-blue-400/10 border-blue-400/20', label: 'Source' },
  entity: { icon: Tag, color: 'text-teal-400 bg-teal-400/10 border-teal-400/20', label: 'Entity' },
}

export default function EntitiesPage() {
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')

  const { data: graph, isLoading } = useQuery({
    queryKey: ['graph'],
    queryFn: api.getGraph,
  })

  const entities = graph?.nodes.filter((n) => n.type !== 'topic' && n.type !== 'subtopic') || []
  const topics = graph?.nodes.filter((n) => n.type === 'topic' || n.type === 'subtopic') || []

  const filtered = entities.filter((e) => {
    const matchesSearch = !search || e.label.toLowerCase().includes(search.toLowerCase())
    const matchesType = typeFilter === 'all' || e.type === typeFilter
    return matchesSearch && matchesType
  })

  const typeCounts = entities.reduce((acc, e) => {
    acc[e.type] = (acc[e.type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">Entities</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Browse and search all entities across your knowledge graph.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-sm mb-xl">
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Total Entities</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">{entities.length}</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Topics</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">{topics.length}</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Relationships</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">{graph?.edges.length || 0}</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Entity Types</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">{Object.keys(typeCounts).length}</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-sm mb-xl">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-md top-1/2 -translate-y-1/2 text-outline" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search entities..."
            className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg pl-10 pr-md py-sm text-on-background font-body-md placeholder:text-outline focus:border-primary focus:outline-none transition-colors"
          />
        </div>
        <div className="flex gap-xs flex-wrap">
          <button
            onClick={() => setTypeFilter('all')}
            className={`px-md py-sm rounded-lg font-label-sm text-label-sm border transition-colors ${
              typeFilter === 'all'
                ? 'bg-primary/10 text-primary border-primary/30'
                : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant hover:border-outline'
            }`}
          >
            All ({entities.length})
          </button>
          {Object.entries(typeCounts).map(([type, count]) => {
            const config = typeConfig[type] || typeConfig.entity
            return (
              <button
                key={type}
                onClick={() => setTypeFilter(type)}
                className={`px-md py-sm rounded-lg font-label-sm text-label-sm border transition-colors ${
                  typeFilter === type
                    ? `${config.color} border-current`
                    : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant hover:border-outline'
                }`}
              >
                {config.label} ({count})
              </button>
            )
          })}
        </div>
      </div>

      {/* Entity List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 rounded-full bg-primary/20 border-2 border-primary text-primary flex items-center justify-center mx-auto animate-pulse-ring">
            <span className="material-symbols-outlined animate-spin" style={{ animationDuration: '3s' }}>sync</span>
          </div>
          <p className="text-on-surface-variant mt-4 font-body-md">Loading entities...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="layer-1 rounded-xl p-lg text-center">
          <Tag size={48} className="mx-auto text-outline mb-4" />
          <p className="text-on-surface-variant text-lg">No entities found</p>
          <p className="text-on-surface-variant text-sm mt-2">
            {search ? 'Try a different search term' : 'Analyze some content to populate the graph'}
          </p>
        </div>
      ) : (
        <div className="grid gap-sm">
          {filtered.map((entity) => {
            const config = typeConfig[entity.type] || typeConfig.entity
            const Icon = config.icon
            return (
              <div
                key={entity.id}
                className="bg-surface-container-lowest border border-outline-variant rounded-lg p-md flex items-center gap-md hover:border-primary/50 card-hover transition-colors"
              >
                <div className={`p-2 rounded-lg border shrink-0 ${config.color}`}>
                  <Icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-body-md text-body-md text-on-surface font-medium truncate">{entity.label}</h3>
                    <span className="font-mono text-mono text-outline text-[11px] px-2 py-0.5 bg-surface-variant rounded border border-outline-variant shrink-0">
                      {entity.type}
                    </span>
                  </div>
                  {entity.properties.description && (
                    <p className="text-sm text-on-surface-variant mt-1 truncate">
                      {String(entity.properties.description)}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {entity.properties.source_url && (
                    <a
                      href={String(entity.properties.source_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-outline hover:text-primary transition-colors"
                    >
                      <span className="material-symbols-outlined text-[18px]">open_in_new</span>
                    </a>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Brain, TrendingUp, GitBranch, Lightbulb, BarChart3, Zap } from 'lucide-react'

export default function AIResearchPage() {
  const { data: graph } = useQuery({
    queryKey: ['graph'],
    queryFn: api.getGraph,
  })

  const { data: videos } = useQuery({
    queryKey: ['videos'],
    queryFn: api.listVideos,
  })

  const nodes = graph?.nodes || []
  const edges = graph?.edges || []

  const entityTypes = nodes.reduce((acc, n) => {
    if (n.type !== 'topic' && n.type !== 'subtopic') {
      acc[n.type] = (acc[n.type] || 0) + 1
    }
    return acc
  }, {} as Record<string, number>)

  const topicNodes = nodes.filter((n) => n.type === 'topic' || n.type === 'subtopic')
  const topTopics = topicNodes.slice(0, 10)

  const avgConnections = nodes.length > 0 ? (edges.length / nodes.length).toFixed(1) : '0'

  return (
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">AI Research</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Insights and analytics from your knowledge graph.
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-sm mb-xl">
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <span className="material-symbols-outlined text-primary text-[20px]">database</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Graph Size</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{nodes.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">nodes</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <GitBranch size={16} className="text-secondary" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Connections</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{edges.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">edges</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <TrendingUp size={16} className="text-green-400" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Avg Connections</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{avgConnections}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">per node</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <div className="flex items-center gap-sm mb-xs">
            <Lightbulb size={16} className="text-purple-400" />
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Topics</span>
          </div>
          <span className="font-h1 text-h1 text-on-surface">{topicNodes.length}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant ml-1">discovered</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-lg mb-xl">
        {/* Entity Distribution */}
        <div className="layer-1 rounded-xl p-lg">
          <div className="flex items-center gap-sm mb-lg">
            <BarChart3 size={18} className="text-primary" />
            <h2 className="font-h2 text-h2 text-on-surface">Entity Distribution</h2>
          </div>
          {Object.keys(entityTypes).length === 0 ? (
            <p className="text-on-surface-variant text-sm text-center py-8">No entities yet</p>
          ) : (
            <div className="space-y-md">
              {Object.entries(entityTypes)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => {
                  const maxCount = Math.max(...Object.values(entityTypes))
                  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0
                  return (
                    <div key={type}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-body-sm text-body-sm text-on-surface capitalize">{type}</span>
                        <span className="font-mono text-mono text-outline text-xs">{count}</span>
                      </div>
                      <div className="w-full bg-surface-variant h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-primary h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </div>

        {/* Top Topics */}
        <div className="layer-1 rounded-xl p-lg">
          <div className="flex items-center gap-sm mb-lg">
            <Lightbulb size={18} className="text-purple-400" />
            <h2 className="font-h2 text-h2 text-on-surface">Top Topics</h2>
          </div>
          {topTopics.length === 0 ? (
            <p className="text-on-surface-variant text-sm text-center py-8">No topics discovered yet</p>
          ) : (
            <div className="space-y-sm">
              {topTopics.map((topic, i) => (
                <div
                  key={topic.id}
                  className="flex items-center gap-md p-sm rounded-lg hover:bg-surface-variant transition-colors"
                >
                  <span className="font-mono text-mono text-outline text-xs w-5 text-right">{i + 1}</span>
                  <span className="font-body-md text-body-md text-on-surface flex-1 truncate">{topic.label}</span>
                  <span className="font-mono text-mono text-outline text-xs px-2 py-0.5 bg-surface-variant rounded border border-outline-variant">
                    {topic.type}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="layer-1 rounded-xl p-lg">
        <div className="flex items-center gap-sm mb-lg">
          <Zap size={18} className="text-yellow-400" />
          <h2 className="font-h2 text-h2 text-on-surface">Recent Analysis Activity</h2>
        </div>
        {!videos || videos.length === 0 ? (
          <p className="text-on-surface-variant text-sm text-center py-8">No analysis activity yet</p>
        ) : (
          <div className="space-y-sm">
            {videos.slice(0, 8).map((video) => (
              <div
                key={video.id}
                className="flex items-center gap-md p-sm rounded-lg hover:bg-surface-variant transition-colors"
              >
                <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center border border-primary/20 shrink-0">
                  <span className="material-symbols-outlined text-primary text-[16px]">link</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-body-sm text-body-sm text-on-surface truncate">{video.title || video.url}</p>
                  <p className="text-xs text-outline truncate">{video.summary}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-mono text-mono text-xs text-outline">
                    {new Date(video.created_at).toLocaleDateString()}
                  </p>
                  <p className="font-mono text-mono text-xs text-primary">{video.entities_count} entities</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

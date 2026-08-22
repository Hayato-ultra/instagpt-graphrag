import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Link } from 'react-router-dom'
import { GitBranch, Tag, FileText, Activity, TrendingUp, Play, Clock } from 'lucide-react'

const stats = [
  { label: 'Sources', value: '124', icon: FileText },
  { label: 'Entities', value: '2.4k', icon: Tag },
  { label: 'Relationships', value: '5.8k', icon: GitBranch },
  { label: 'Topics', value: '42', icon: TrendingUp },
  { label: 'Active Jobs', value: '2', icon: Activity, pulse: true },
]

export default function HomePage() {
  const { data: videos } = useQuery({
    queryKey: ['videos'],
    queryFn: api.listVideos,
  })

  return (
    <div className="p-lg max-w-container-max mx-auto">
      {/* Header */}
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">Knowledge Overview</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Explore, analyze, and grow your personal knowledge graph.
        </p>
      </div>

      {/* Stats Bento */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-sm mb-xl">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.label} className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg flex flex-col justify-between hover:border-primary/50 transition-colors card-hover">
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">{stat.label}</span>
              <div className="flex items-center gap-xs mt-sm">
                {stat.pulse && <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />}
                <span className="font-h1 text-h1 text-on-surface">{stat.value}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-lg mb-xl">
        <Link to="/analyze" className="layer-1 rounded-xl p-lg card-hover transition-colors group">
          <div className="flex items-center gap-3 mb-md">
            <div className="w-12 h-12 rounded bg-primary/10 flex items-center justify-center border border-primary/20">
              <span className="material-symbols-outlined text-primary text-[24px]">link</span>
            </div>
            <div>
              <h2 className="font-h2 text-h2 text-on-surface">Analyze Content</h2>
              <p className="font-body-md text-body-md text-on-surface-variant">Inject new data via URL</p>
            </div>
          </div>
          <div className="w-full bg-surface-variant h-1 rounded-full overflow-hidden">
            <div className="bg-primary h-full rounded-full w-0 group-hover:w-full transition-all duration-500" />
          </div>
        </Link>

        <Link to="/graph" className="layer-1 rounded-xl p-lg card-hover transition-colors group">
          <div className="flex items-center gap-3 mb-md">
            <div className="w-12 h-12 rounded bg-secondary/10 flex items-center justify-center border border-secondary/20">
              <span className="material-symbols-outlined text-secondary text-[24px]">account_tree</span>
            </div>
            <div>
              <h2 className="font-h2 text-h2 text-on-surface">Knowledge Graph</h2>
              <p className="font-body-md text-body-md text-on-surface-variant">Explore entity relationships</p>
            </div>
          </div>
          <div className="w-full bg-surface-variant h-1 rounded-full overflow-hidden">
            <div className="bg-secondary h-full rounded-full w-0 group-hover:w-full transition-all duration-500" />
          </div>
        </Link>
      </div>

      {/* Recent Videos */}
      <div>
        <div className="flex items-center justify-between mb-md">
          <h2 className="font-h2 text-h2 text-on-surface">Recent Sources</h2>
          <Link to="/search" className="font-label-sm text-label-sm text-primary hover:underline">View All</Link>
        </div>
        {videos && videos.length === 0 && (
          <div className="layer-1 rounded-xl p-lg text-center">
            <FileText size={48} className="mx-auto text-outline mb-4" />
            <p className="text-on-surface-variant text-lg">No sources analyzed yet</p>
            <p className="text-on-surface-variant text-sm mt-2">
              Paste a URL in the Analyze page to get started
            </p>
          </div>
        )}
        <div className="grid gap-sm">
          {videos?.map((video) => (
            <Link
              key={video.id}
              to="/graph"
              className="bg-surface-container-lowest border border-outline-variant rounded-lg p-md flex items-center gap-md hover:border-primary/50 card-hover transition-colors"
            >
              {video.thumbnail ? (
                <img src={video.thumbnail} alt="" className="w-20 h-12 object-cover rounded" />
              ) : (
                <div className="w-20 h-12 bg-surface-variant rounded flex items-center justify-center">
                  <Play size={16} className="text-outline" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h3 className="font-body-md text-body-md text-on-surface truncate">{video.title || video.youtube_id}</h3>
                <p className="text-sm text-on-surface-variant truncate">{video.summary}</p>
              </div>
              <div className="font-mono text-mono text-outline flex items-center gap-1 shrink-0">
                <Clock size={12} />
                {new Date(video.created_at).toLocaleDateString()}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

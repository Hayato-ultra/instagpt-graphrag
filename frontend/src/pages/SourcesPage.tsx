import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Link } from 'react-router-dom'
import { FileText, Play, Clock, Tag, ExternalLink, Search, Filter } from 'lucide-react'

export default function SourcesPage() {
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<'date' | 'entities'>('date')

  const { data: videos, isLoading } = useQuery({
    queryKey: ['videos'],
    queryFn: api.listVideos,
  })

  const sorted = (videos || [])
    .filter((v) => !search || v.title?.toLowerCase().includes(search.toLowerCase()) || v.url.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === 'entities') return (b.entities_count || 0) - (a.entities_count || 0)
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  return (
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">Sources</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          All content that has been analyzed and added to the knowledge graph.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-sm mb-xl">
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Total Sources</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">{videos?.length || 0}</span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Total Entities</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">
            {videos?.reduce((sum, v) => sum + (v.entities_count || 0), 0) || 0}
          </span>
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-md rounded-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">This Week</span>
          <span className="font-h1 text-h1 text-on-surface block mt-xs">
            {videos?.filter((v) => {
              const d = new Date(v.created_at)
              const now = new Date()
              return (now.getTime() - d.getTime()) < 7 * 24 * 60 * 60 * 1000
            }).length || 0}
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col md:flex-row gap-sm mb-xl">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-md top-1/2 -translate-y-1/2 text-outline" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search sources..."
            className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg pl-10 pr-md py-sm text-on-background font-body-md placeholder:text-outline focus:border-primary focus:outline-none transition-colors"
          />
        </div>
        <div className="flex gap-xs">
          <button
            onClick={() => setSortBy('date')}
            className={`px-md py-sm rounded-lg font-label-sm text-label-sm border transition-colors flex items-center gap-1 ${
              sortBy === 'date'
                ? 'bg-primary/10 text-primary border-primary/30'
                : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant hover:border-outline'
            }`}
          >
            <Clock size={14} />
            Recent
          </button>
          <button
            onClick={() => setSortBy('entities')}
            className={`px-md py-sm rounded-lg font-label-sm text-label-sm border transition-colors flex items-center gap-1 ${
              sortBy === 'entities'
                ? 'bg-primary/10 text-primary border-primary/30'
                : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant hover:border-outline'
            }`}
          >
            <Filter size={14} />
            Most Entities
          </button>
        </div>
      </div>

      {/* Source List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 rounded-full bg-primary/20 border-2 border-primary text-primary flex items-center justify-center mx-auto animate-pulse-ring">
            <span className="material-symbols-outlined animate-spin" style={{ animationDuration: '3s' }}>sync</span>
          </div>
          <p className="text-on-surface-variant mt-4 font-body-md">Loading sources...</p>
        </div>
      ) : sorted.length === 0 ? (
        <div className="layer-1 rounded-xl p-lg text-center">
          <FileText size={48} className="mx-auto text-outline mb-4" />
          <p className="text-on-surface-variant text-lg">No sources found</p>
          <p className="text-on-surface-variant text-sm mt-2">
            {search ? 'Try a different search term' : 'Analyze a URL to get started'}
          </p>
          {!search && (
            <Link to="/analyze" className="mt-4 inline-flex items-center gap-sm bg-primary/10 text-primary px-md py-sm rounded-lg border border-primary/30 hover:bg-primary/20 transition-colors font-label-sm">
              <span className="material-symbols-outlined text-[16px]">add</span>
              Analyze Content
            </Link>
          )}
        </div>
      ) : (
        <div className="grid gap-sm">
          {sorted.map((video) => (
            <Link
              key={video.id}
              to="/graph"
              className="bg-surface-container-lowest border border-outline-variant rounded-lg p-md flex items-center gap-md hover:border-primary/50 card-hover transition-colors group"
            >
              {video.thumbnail ? (
                <img src={video.thumbnail} alt="" className="w-24 h-14 object-cover rounded shrink-0" />
              ) : (
                <div className="w-24 h-14 bg-surface-variant rounded flex items-center justify-center shrink-0">
                  <Play size={20} className="text-outline" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h3 className="font-body-md text-body-md text-on-surface truncate group-hover:text-primary transition-colors">
                  {video.title || video.url}
                </h3>
                <p className="text-sm text-on-surface-variant truncate mt-1">{video.summary}</p>
                <div className="flex items-center gap-md mt-2">
                  <span className="flex items-center gap-1 text-xs text-outline">
                    <Tag size={12} />
                    {video.entities_count} entities
                  </span>
                  <span className="flex items-center gap-1 text-xs text-outline">
                    <Clock size={12} />
                    {new Date(video.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <ExternalLink size={16} className="text-outline group-hover:text-primary transition-colors shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

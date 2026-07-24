import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../services/api'
import { Search, Video, Lightbulb, Wrench, Layers, Workflow } from 'lucide-react'

const typeIcons: Record<string, typeof Video> = {
  video: Video,
  topic: Lightbulb,
  subtopic: Lightbulb,
  tool: Wrench,
  concept: Layers,
  workflow: Workflow,
  tip: Lightbulb,
  bugfix: Lightbulb,
}

const typeColors: Record<string, string> = {
  video: 'text-blue-400 bg-blue-400/10',
  topic: 'text-purple-400 bg-purple-400/10',
  subtopic: 'text-violet-300 bg-violet-400/10',
  tool: 'text-orange-400 bg-orange-400/10',
  concept: 'text-green-400 bg-green-400/10',
  workflow: 'text-pink-400 bg-pink-400/10',
  tip: 'text-pink-300 bg-pink-400/10',
  bugfix: 'text-red-400 bg-red-400/10',
}

export default function SearchPage() {
  const [query, setQuery] = useState('')

  const searchMutation = useMutation({
    mutationFn: (q: string) => api.search(q),
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      searchMutation.mutate(query.trim())
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Search</h1>

      <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search videos, topics, tools, concepts..."
              className="w-full bg-surface border border-border rounded-lg pl-10 pr-4 py-3 text-text placeholder-muted focus:outline-none focus:border-accent"
            />
          </div>
          <button
            type="submit"
            disabled={searchMutation.isPending || !query.trim()}
            className="bg-accent text-bg px-6 py-3 rounded-lg font-medium hover:opacity-90 disabled:opacity-50"
          >
            Search
          </button>
        </div>
      </form>

      {searchMutation.isPending && (
        <div className="text-center py-12 text-muted">Searching...</div>
      )}

      {searchMutation.data && (
        <div>
          <p className="text-sm text-muted mb-4">
            {searchMutation.data.total} results found
          </p>

          {searchMutation.data.results.length === 0 && (
            <p className="text-center py-12 text-muted">No results found</p>
          )}

          <div className="space-y-3">
            {searchMutation.data.results.map((result, i) => {
              const Icon = typeIcons[result.type] || Layers
              return (
                <div
                  key={i}
                  className="bg-surface border border-border rounded-lg p-4 hover:border-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${typeColors[result.type] || 'text-muted bg-muted/10'}`}>
                      <Icon size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium">{result.name}</h3>
                        <span className="text-xs text-muted px-2 py-0.5 bg-border rounded">
                          {result.type}
                        </span>
                      </div>
                      {result.description && (
                        <p className="text-sm text-muted mt-1 truncate">
                          {result.description}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

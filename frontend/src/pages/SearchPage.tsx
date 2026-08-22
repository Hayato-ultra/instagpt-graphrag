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
  video: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  topic: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
  subtopic: 'text-violet-300 bg-violet-400/10 border-violet-400/20',
  tool: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
  concept: 'text-green-400 bg-green-400/10 border-green-400/20',
  workflow: 'text-pink-400 bg-pink-400/10 border-pink-400/20',
  tip: 'text-pink-300 bg-pink-400/10 border-pink-400/20',
  bugfix: 'text-red-400 bg-red-400/10 border-red-400/20',
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
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">Semantic Search</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Ask your knowledge graph questions in natural language.
        </p>
      </div>

      {/* Search Input */}
      <form onSubmit={handleSearch} className="mb-xl">
        <div className="relative flex items-center w-full layer-2 rounded-lg shadow-sm focus-within:border-primary transition-colors group">
          <div className="pl-md text-outline">
            <Search size={20} />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find connections between React & WebGL..."
            className="w-full bg-transparent border-none text-on-background font-mono text-mono placeholder:text-outline focus:ring-0 py-lg px-md"
          />
          <div className="pr-sm py-sm">
            <button
              type="submit"
              disabled={searchMutation.isPending || !query.trim()}
              className="bg-inverse-primary hover:bg-primary-container text-white font-label-sm text-label-sm px-lg py-sm rounded border-t border-white/20 transition-all active:scale-95 flex items-center gap-sm disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[16px]">bolt</span>
              Search
            </button>
          </div>
        </div>
      </form>

      {/* Results */}
      {searchMutation.isPending && (
        <div className="text-center py-12">
          <div className="w-12 h-12 rounded-full bg-primary/20 border-2 border-primary text-primary flex items-center justify-center mx-auto animate-pulse-ring">
            <span className="material-symbols-outlined animate-spin" style={{ animationDuration: '3s' }}>sync</span>
          </div>
          <p className="text-on-surface-variant mt-4 font-body-md">Searching knowledge graph...</p>
        </div>
      )}

      {searchMutation.data && (
        <div>
          <p className="font-mono text-mono text-on-surface-variant mb-md">
            {searchMutation.data.total} results found
          </p>

          {searchMutation.data.results.length === 0 && (
            <div className="layer-1 rounded-xl p-lg text-center">
              <Search size={48} className="mx-auto text-outline mb-4" />
              <p className="text-on-surface-variant text-lg">No results found</p>
            </div>
          )}

          <div className="space-y-sm">
            {searchMutation.data.results.map((result, i) => {
              const Icon = typeIcons[result.type] || Layers
              return (
                <div
                  key={i}
                  className="layer-1 rounded-lg p-md card-hover transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg border ${typeColors[result.type] || 'text-outline bg-outline/10 border-outline/20'}`}>
                      <Icon size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-body-md text-body-md text-on-surface font-medium">{result.name}</h3>
                        <span className="font-mono text-mono text-outline text-[11px] px-2 py-0.5 bg-surface-variant rounded border border-outline-variant">
                          {result.type}
                        </span>
                      </div>
                      {result.description && (
                        <p className="text-sm text-on-surface-variant mt-1 truncate">
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

import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { BookOpen, Clock } from 'lucide-react'

export default function NotebookPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['notebook'],
    queryFn: api.listNotebook,
  })

  return (
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl">
        <div className="flex items-center gap-3 mb-2">
          <span className="material-symbols-outlined text-primary text-[28px]">menu_book</span>
          <h1 className="font-display text-display text-on-surface">Notebook</h1>
        </div>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          AI-generated notes from your analyzed content.
        </p>
      </div>

      {isLoading && (
        <div className="text-center py-12">
          <div className="w-12 h-12 rounded-full bg-primary/20 border-2 border-primary text-primary flex items-center justify-center mx-auto animate-pulse-ring">
            <span className="material-symbols-outlined animate-spin" style={{ animationDuration: '3s' }}>sync</span>
          </div>
          <p className="text-on-surface-variant mt-4 font-body-md">Loading notebook...</p>
        </div>
      )}

      {!isLoading && data?.entries.length === 0 && (
        <div className="layer-1 rounded-xl p-lg text-center">
          <span className="material-symbols-outlined text-[48px] text-outline mb-4 block">menu_book</span>
          <p className="text-on-surface-variant text-lg">No notebook entries yet</p>
          <p className="text-on-surface-variant text-sm mt-2">
            Analyze a video to automatically create notebook entries
          </p>
        </div>
      )}

      <div className="space-y-md">
        {data?.entries.map((entry) => (
          <div
            key={entry.id}
            className="layer-1 rounded-xl p-lg card-hover transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-h2 text-h2 text-on-surface">{entry.title}</h3>
              <span className="font-mono text-mono text-outline flex items-center gap-1 shrink-0">
                <Clock size={12} />
                {new Date(entry.created_at).toLocaleDateString()}
              </span>
            </div>

            {entry.summary && (
              <p className="font-body-md text-body-md text-on-surface-variant mb-3">{entry.summary}</p>
            )}

            {entry.ai_notes && (
              <div className="mt-3 layer-2 p-md rounded-lg border-l-2 border-l-primary">
                <h4 className="font-label-sm text-label-sm text-primary mb-1">AI Notes</h4>
                <p className="font-body-md text-body-md text-on-surface">{entry.ai_notes}</p>
              </div>
            )}

            {entry.tags && (
              <div className="mt-3 flex flex-wrap gap-2">
                {entry.tags.split(',').map((tag, i) => (
                  <span
                    key={i}
                    className="font-mono text-[11px] px-2 py-1 rounded bg-primary/10 text-primary border border-primary/20"
                  >
                    {tag.trim()}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

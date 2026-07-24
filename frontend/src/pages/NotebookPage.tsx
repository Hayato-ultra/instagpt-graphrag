import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { BookOpen, Clock } from 'lucide-react'

export default function NotebookPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['notebook'],
    queryFn: api.listNotebook,
  })

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <BookOpen size={28} className="text-accent" />
        <h1 className="text-3xl font-bold">Notebook</h1>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-muted">Loading...</div>
      )}

      {!isLoading && data?.entries.length === 0 && (
        <div className="text-center py-12">
          <BookOpen size={48} className="mx-auto text-muted mb-4" />
          <p className="text-muted text-lg">No notebook entries yet</p>
          <p className="text-muted text-sm mt-2">
            Analyze a video to automatically create notebook entries
          </p>
        </div>
      )}

      <div className="space-y-4">
        {data?.entries.map((entry) => (
          <div
            key={entry.id}
            className="bg-surface border border-border rounded-lg p-5 hover:border-accent/50 transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-lg font-semibold">{entry.title}</h3>
              <span className="text-xs text-muted flex items-center gap-1">
                <Clock size={12} />
                {new Date(entry.created_at).toLocaleDateString()}
              </span>
            </div>

            {entry.summary && (
              <p className="text-sm text-muted mb-3">{entry.summary}</p>
            )}

            {entry.ai_notes && (
              <div className="mt-3 p-3 bg-bg rounded border border-border">
                <h4 className="text-xs font-medium text-muted mb-1">AI Notes</h4>
                <p className="text-sm">{entry.ai_notes}</p>
              </div>
            )}

            {entry.tags && (
              <div className="mt-3 flex flex-wrap gap-2">
                {entry.tags.split(',').map((tag, i) => (
                  <span
                    key={i}
                    className="text-xs bg-accent/10 text-accent px-2 py-1 rounded"
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

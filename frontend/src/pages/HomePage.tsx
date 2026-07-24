import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { useNavigate } from 'react-router-dom'
import { Play, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'

export default function HomePage() {
  const [url, setUrl] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: videos } = useQuery({
    queryKey: ['videos'],
    queryFn: api.listVideos,
  })

  const analyzeMutation = useMutation({
    mutationFn: (videoUrl: string) => api.analyzeVideo(videoUrl),
    onSuccess: (data) => {
      setUrl('')
      pollAnalysis(data.analysis_id)
    },
  })

  const pollAnalysis = async (analysisId: string) => {
    const poll = async () => {
      const status = await api.getAnalysisStatus(analysisId)
      if (status.status === 'completed') {
        queryClient.invalidateQueries({ queryKey: ['videos'] })
        if (status.video_id) {
          navigate('/graph')
        }
        return
      }
      if (status.status === 'failed') {
        return
      }
      setTimeout(poll, 2000)
    }
    poll()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      analyzeMutation.mutate(url.trim())
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4 text-accent">
          Knowledge Graph AI
        </h1>
        <p className="text-muted text-lg">
          Paste a YouTube URL and get an AI-powered knowledge graph
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mb-12">
        <div className="flex gap-3">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="flex-1 bg-surface border border-border rounded-lg px-4 py-3 text-text placeholder-muted focus:outline-none focus:border-accent"
            disabled={analyzeMutation.isPending}
          />
          <button
            type="submit"
            disabled={analyzeMutation.isPending || !url.trim()}
            className="bg-accent text-bg px-6 py-3 rounded-lg font-medium flex items-center gap-2 hover:opacity-90 disabled:opacity-50"
          >
            {analyzeMutation.isPending ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Play size={20} />
            )}
            Analyze
          </button>
        </div>
        {analyzeMutation.isError && (
          <p className="mt-2 text-red-400 text-sm">
            {analyzeMutation.error.message}
          </p>
        )}
      </form>

      <div>
        <h2 className="text-xl font-semibold mb-4">Recent Videos</h2>
        {videos && videos.length === 0 && (
          <p className="text-muted">No videos analyzed yet. Paste a URL above to get started.</p>
        )}
        <div className="grid gap-3">
          {videos?.map((video) => (
            <div
              key={video.id}
              className="bg-surface border border-border rounded-lg p-4 flex items-center gap-4 hover:border-accent/50 cursor-pointer transition-colors"
              onClick={() => navigate('/graph')}
            >
              {video.thumbnail ? (
                <img src={video.thumbnail} alt="" className="w-20 h-12 object-cover rounded" />
              ) : (
                <div className="w-20 h-12 bg-border rounded flex items-center justify-center">
                  <Play size={16} className="text-muted" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h3 className="font-medium truncate">{video.title || video.youtube_id}</h3>
                <p className="text-sm text-muted truncate">{video.summary}</p>
              </div>
              <div className="text-xs text-muted flex items-center gap-1">
                <Clock size={12} />
                {new Date(video.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

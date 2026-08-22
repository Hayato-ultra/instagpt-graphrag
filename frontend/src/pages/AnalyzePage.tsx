import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'

interface PipelineStep {
  label: string
  icon: string
  status: 'done' | 'active' | 'pending'
  progress?: number
}

export default function AnalyzePage() {
  const [url, setUrl] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([
    { label: 'Content Extraction', icon: 'download', status: 'pending' },
    { label: 'Semantic Chunking', icon: 'science', status: 'pending' },
    { label: 'Vector Embedding', icon: 'psychology', status: 'pending' },
    { label: 'Entity Enrichment', icon: 'auto_awesome', status: 'pending' },
    { label: 'Graph Resolution', icon: 'hub', status: 'pending' },
  ])

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
    <div className="p-lg max-w-container-max mx-auto">
      {/* Header */}
      <div className="mb-xl">
        <h1 className="font-display text-display text-on-surface mb-xs">Analyze Content</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Inject new data into the GraphRAG pipeline via URL.
        </p>
      </div>

      {/* URL Input */}
      <div className="relative flex items-center w-full bg-surface-container-high border border-outline-variant rounded-lg shadow-sm focus-within:border-primary transition-colors mb-xl group">
        <div className="pl-md text-outline">
          <span className="material-symbols-outlined">link</span>
        </div>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.instagram.com/reel/CwXYZ123ABC/"
          className="w-full bg-transparent border-none text-on-background font-mono text-mono placeholder:text-outline focus:ring-0 py-lg px-md"
          disabled={analyzeMutation.isPending}
        />
        <div className="pr-sm py-sm">
          <button
            onClick={handleSubmit}
            disabled={analyzeMutation.isPending || !url.trim()}
            className="bg-inverse-primary hover:bg-primary-container text-white font-label-sm text-label-sm px-lg py-sm rounded border-t border-white/20 transition-all active:scale-95 flex items-center gap-sm disabled:opacity-50"
          >
            {analyzeMutation.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <span className="material-symbols-outlined text-[16px]">bolt</span>
            )}
            Analyze
          </button>
        </div>
      </div>

      {analyzeMutation.isError && (
        <div className="layer-1 rounded-lg p-md border-error/50 border mb-xl">
          <div className="flex items-center gap-2 text-error">
            <XCircle size={18} />
            <span className="font-body-md text-body-md">{analyzeMutation.error.message}</span>
          </div>
        </div>
      )}

      {/* Pipeline Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
        {/* URL Preview */}
        <section className="lg:col-span-5 flex flex-col gap-md">
          <h2 className="font-h2 text-h2 text-on-surface flex items-center gap-sm">
            <span className="material-symbols-outlined text-outline">preview</span>
            Target Context
          </h2>
          <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-md flex flex-col gap-md hover:border-primary/50 transition-colors h-full">
            <div className="flex items-start justify-between border-b border-outline-variant pb-md">
              <div className="flex gap-md items-center">
                <div className="w-12 h-12 bg-surface-variant rounded flex items-center justify-center text-primary-fixed-dim">
                  <span className="material-symbols-outlined text-[24px]">movie</span>
                </div>
                <div>
                  <div className="font-body-md text-body-md text-on-background font-medium">Instagram Reel</div>
                  <div className="font-mono text-mono text-on-surface-variant">instagram.com</div>
                </div>
              </div>
              <span className="bg-secondary/10 text-secondary font-label-sm text-label-sm px-2 py-1 rounded-full border border-secondary/20">Verified Domain</span>
            </div>
            <div className="space-y-sm flex-1">
              <div>
                <span className="font-label-sm text-label-sm text-outline uppercase tracking-widest block mb-xs">Detected Modalities</span>
                <div className="flex gap-sm mt-xs">
                  <span className="border border-outline-variant bg-surface-container-high text-on-surface font-mono text-mono px-2 py-1 rounded text-xs">Video</span>
                  <span className="border border-outline-variant bg-surface-container-high text-on-surface font-mono text-mono px-2 py-1 rounded text-xs">Audio (Speech)</span>
                  <span className="border border-outline-variant bg-surface-container-high text-on-surface font-mono text-mono px-2 py-1 rounded text-xs">OCR Text</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pipeline */}
        <section className="lg:col-span-7 flex flex-col gap-md">
          <h2 className="font-h2 text-h2 text-on-surface flex items-center gap-sm">
            <span className="material-symbols-outlined text-outline">account_tree</span>
            GraphRAG Pipeline
          </h2>
          <div className="bg-surface-container-lowest border border-outline-variant rounded-lg p-lg flex flex-col gap-0 h-full relative overflow-hidden">
            {/* Connecting Line */}
            <div className="absolute left-[39px] top-lg bottom-lg w-[2px] bg-outline-variant/30 z-0 hidden sm:block" />

            {/* Steps */}
            <div className="space-y-xl relative z-10 flex flex-col h-full justify-between">
              {pipelineSteps.map((step, i) => (
                <div key={i} className={`flex items-start gap-md group ${step.status === 'pending' ? 'opacity-50' : ''}`}>
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center shrink-0 z-10 relative ${
                    step.status === 'done' ? 'bg-secondary-container/20 border border-secondary text-secondary' :
                    step.status === 'active' ? 'bg-primary/20 border-2 border-primary text-primary animate-pulse-ring' :
                    'bg-surface-variant border border-outline-variant text-outline'
                  }`}>
                    {step.status === 'done' ? (
                      <span className="material-symbols-outlined text-[20px]">check</span>
                    ) : step.status === 'active' ? (
                      <span className="material-symbols-outlined text-[20px] animate-spin" style={{ animationDuration: '3s' }}>sync</span>
                    ) : (
                      <span className="material-symbols-outlined text-[20px]">{step.icon}</span>
                    )}
                  </div>
                  <div className="flex-1 pt-xs">
                    <div className="flex justify-between items-center mb-xs">
                      <h3 className={`font-body-lg text-body-lg font-medium ${step.status === 'active' ? 'text-primary' : 'text-on-background'}`}>
                        {i + 1}. {step.label}
                      </h3>
                      <span className={`font-mono text-mono ${
                        step.status === 'done' ? 'text-secondary' :
                        step.status === 'active' ? 'text-primary animate-pulse' :
                        'text-outline'
                      }`}>
                        {step.status === 'done' ? '100%' :
                         step.status === 'active' ? `${step.progress || 0}%` :
                         'Pending'}
                      </span>
                    </div>
                    {step.status === 'active' && step.progress && (
                      <div className="w-full bg-surface-variant h-1 mt-sm rounded-full overflow-hidden">
                        <div className="bg-primary h-full rounded-full transition-all duration-500" style={{ width: `${step.progress}%` }} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

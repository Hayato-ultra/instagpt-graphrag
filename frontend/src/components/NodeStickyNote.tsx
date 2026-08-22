import { useState, useRef, useCallback, useEffect } from 'react'
import { X, ExternalLink, Pencil, GitMerge, Check, Loader2, GripVertical } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

interface StickyNode {
  id: string
  label: string
  type: string
  description?: string
  properties?: Record<string, any>
}

interface NodeStickyNoteProps {
  node: StickyNode
  allNodes: StickyNode[]
  onClose: () => void
}

const typeColors: Record<string, string> = {
  video: '#58a6ff', topic: '#a371f7', subtopic: '#c297ff',
  tool: '#f0883e', concept: '#3fb950', workflow: '#d2a8ff',
  tip: '#f778ba', bugfix: '#f85149', platform: '#79c0ff',
  library: '#8b949e', web_app: '#7ee787', framework: '#d2a8ff',
  entity: '#58a6ff', creative_software: '#d2a8ff',
}

function parseJsonArray(val: unknown): string[] | null {
  if (typeof val !== 'string') return null
  try {
    const parsed = JSON.parse(val)
    return Array.isArray(parsed) ? parsed : null
  } catch { return null }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[11px] text-outline uppercase tracking-wider mb-1 block">{label}</label>
      {children}
    </div>
  )
}

export default function NodeStickyNote({ node, allNodes, onClose }: NodeStickyNoteProps) {
  const color = typeColors[node.type] || '#8b949e'
  const props = node.properties || {}
  const queryClient = useQueryClient()

  const [pos, setPos] = useState({ x: window.innerWidth / 2 - 210, y: window.innerHeight / 2 - 200 })
  const dragRef = useRef<HTMLDivElement>(null)
  const dragState = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 })

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button, input, textarea, select, a')) return
    dragState.current = { dragging: true, startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y }
    const onMouseMove = (e: MouseEvent) => {
      if (!dragState.current.dragging) return
      setPos({
        x: dragState.current.origX + (e.clientX - dragState.current.startX),
        y: dragState.current.origY + (e.clientY - dragState.current.startY),
      })
    }
    const onMouseUp = () => {
      dragState.current.dragging = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [pos.x, pos.y])

  useEffect(() => {
    setPos({ x: window.innerWidth / 2 - 210, y: window.innerHeight / 2 - 200 })
  }, [node.id])

  const [mode, setMode] = useState<'view' | 'edit' | 'merge'>('view')
  const [editFields, setEditFields] = useState({
    description: node.description || '',
    summary: (props.summary as string) || '',
    source_url: (props.source_url as string) || '',
    key_points: (props.key_points as string) || '[]',
  })
  const [mergeTarget, setMergeTarget] = useState('')
  const [mergeName, setMergeName] = useState('')

  const editMutation = useMutation({
    mutationFn: () => api.editNode(node.id, editFields),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['graph'] }); setMode('view') },
  })

  const mergeMutation = useMutation({
    mutationFn: () => api.mergeNodes(node.id, mergeTarget, mergeName || undefined),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['graph'] }); onClose() },
  })

  const keyPoints = parseJsonArray(props.key_points)
  const candidates = allNodes.filter((n) => n.id !== node.id)

  return (
    <div
      ref={dragRef}
      className="fixed z-50 w-[420px] max-h-[80vh] rounded-xl shadow-2xl border overflow-hidden flex flex-col"
      style={{
        left: pos.x, top: pos.y,
        borderColor: color,
        backgroundColor: 'rgba(24,24,28,0.97)',
        backdropFilter: 'blur(12px)',
        boxShadow: `0 0 40px ${color}30, 0 8px 32px rgba(0,0,0,0.5)`,
      }}
    >
      <div
        onMouseDown={onMouseDown}
        className="flex items-center justify-between px-4 py-3 cursor-grab active:cursor-grabbing select-none"
        style={{ borderBottom: `1px solid ${color}40` }}
      >
        <div className="flex items-center gap-3">
          <GripVertical size={14} className="text-outline opacity-50" />
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
          <div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color }}>{node.type}</div>
            {mode === 'edit' ? (
              <div className="text-on-surface font-medium">{node.label}</div>
            ) : (
              <div className="text-on-surface font-medium">{node.label}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {mode === 'view' && (
            <>
              <button onClick={() => setMode('edit')} className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-white/10 transition-colors" title="Edit">
                <Pencil size={13} className="text-on-surface-variant" />
              </button>
              <button onClick={() => setMode('merge')} className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-white/10 transition-colors" title="Merge">
                <GitMerge size={13} className="text-on-surface-variant" />
              </button>
            </>
          )}
          <button onClick={onClose} className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-white/10 transition-colors">
            <X size={14} className="text-on-surface-variant" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {mode === 'view' && (
          <>
            {node.description && (
              <section>
                <h4 className="text-[11px] text-outline uppercase tracking-wider mb-1.5">Description</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed">{node.description}</p>
              </section>
            )}
            {props.summary && props.summary !== node.description && (
              <section>
                <h4 className="text-[11px] text-outline uppercase tracking-wider mb-1.5">Summary</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed">{props.summary as string}</p>
              </section>
            )}
            {props.source_url && (
              <section>
                <h4 className="text-[11px] text-outline uppercase tracking-wider mb-1.5">Link</h4>
                <a href={props.source_url as string} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm hover:underline" style={{ color }}>
                  {props.source_url as string}
                  <ExternalLink size={12} />
                </a>
              </section>
            )}
            {keyPoints && keyPoints.length > 0 && (
              <section>
                <h4 className="text-[11px] text-outline uppercase tracking-wider mb-1.5">Key Points</h4>
                <ul className="space-y-1">
                  {keyPoints.map((p: string, i: number) => (
                    <li key={i} className="text-sm text-on-surface-variant flex gap-2">
                      <span style={{ color }} className="mt-0.5">•</span><span>{p}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {!node.description && !props.summary && !props.source_url && (!keyPoints || keyPoints.length === 0) && (
              <div className="space-y-2">
                {props.name && (
                  <div className="flex justify-between text-sm">
                    <span className="text-outline">Name</span>
                    <span className="text-on-surface">{props.name as string}</span>
                  </div>
                )}
                {props.parent_topic && (
                  <div className="flex justify-between text-sm">
                    <span className="text-outline">Parent topic</span>
                    <span className="text-on-surface">{props.parent_topic as string}</span>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {mode === 'edit' && (
          <div className="space-y-3">
            <Field label="Description">
              <textarea value={editFields.description} onChange={(e) => setEditFields((f) => ({ ...f, description: e.target.value }))} rows={3}
                className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary resize-none" />
            </Field>
            <Field label="Summary">
              <textarea value={editFields.summary} onChange={(e) => setEditFields((f) => ({ ...f, summary: e.target.value }))} rows={2}
                className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary resize-none" />
            </Field>
            <Field label="Source URL">
              <input value={editFields.source_url} onChange={(e) => setEditFields((f) => ({ ...f, source_url: e.target.value }))} placeholder="https://..."
                className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary" />
            </Field>
            <Field label="Key Points (JSON array)">
              <textarea value={editFields.key_points} onChange={(e) => setEditFields((f) => ({ ...f, key_points: e.target.value }))} rows={3}
                className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface font-mono outline-none focus:border-primary resize-none" />
            </Field>
            <div className="flex gap-2 pt-2">
              <button onClick={() => editMutation.mutate()} disabled={editMutation.isPending}
                className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium text-white transition-colors"
                style={{ backgroundColor: color }}>
                {editMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Save
              </button>
              <button onClick={() => setMode('view')} className="px-4 py-2 rounded-lg text-sm border border-outline-variant text-on-surface-variant hover:bg-surface-variant transition-colors">Cancel</button>
            </div>
            {editMutation.isError && <p className="text-xs text-red-400">Failed to save.</p>}
          </div>
        )}

        {mode === 'merge' && (
          <div className="space-y-3">
            <p className="text-sm text-on-surface-variant">
              Merge <span className="text-on-surface font-medium">{node.label}</span> into another node. Relationships transfer, this node is deleted.
            </p>
            <Field label="Target node">
              <select value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}
                className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary">
                <option value="">Select a node...</option>
                {candidates.map((n) => (
                  <option key={n.id} value={n.id}>{n.label} ({n.type})</option>
                ))}
              </select>
            </Field>
            <Field label="Merged name (optional)">
              <input value={mergeName} onChange={(e) => setMergeName(e.target.value)} placeholder={node.label}
                className="w-full bg-surface-variant border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface outline-none focus:border-primary" />
            </Field>
            <div className="flex gap-2 pt-2">
              <button onClick={() => mergeMutation.mutate()} disabled={!mergeTarget || mergeMutation.isPending}
                className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-500 disabled:opacity-40 transition-colors">
                {mergeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <GitMerge size={14} />}
                Merge
              </button>
              <button onClick={() => setMode('view')} className="px-4 py-2 rounded-lg text-sm border border-outline-variant text-on-surface-variant hover:bg-surface-variant transition-colors">Cancel</button>
            </div>
            {mergeMutation.isError && <p className="text-xs text-red-400">Merge failed.</p>}
          </div>
        )}
      </div>
    </div>
  )
}

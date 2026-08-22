import { useState } from 'react'
import { Settings, Database, Cpu, Globe, Key, Save, CheckCircle } from 'lucide-react'

interface SettingGroup {
  id: string
  label: string
  icon: typeof Settings
  settings: Array<{
    key: string
    label: string
    type: 'text' | 'password' | 'select' | 'toggle'
    placeholder?: string
    options?: string[]
    value: string
  }>
}

const defaultSettings: SettingGroup[] = [
  {
    id: 'llm',
    label: 'LLM Provider',
    icon: Cpu,
    settings: [
      { key: 'llm_provider', label: 'Provider', type: 'select', options: ['openai', 'openrouter', 'nvidia', 'google', 'ollama'], value: 'openai' },
      { key: 'llm_model', label: 'Model', type: 'text', placeholder: 'gpt-4o-mini', value: 'gpt-4o-mini' },
      { key: 'llm_api_key', label: 'API Key', type: 'password', placeholder: 'sk-...', value: '' },
    ],
  },
  {
    id: 'embedding',
    label: 'Embeddings',
    icon: Cpu,
    settings: [
      { key: 'embedding_provider', label: 'Provider', type: 'select', options: ['openai', 'nvidia', 'google', 'ollama'], value: 'openai' },
      { key: 'embedding_model', label: 'Model', type: 'text', placeholder: 'text-embedding-3-small', value: 'text-embedding-3-small' },
    ],
  },
  {
    id: 'database',
    label: 'Databases',
    icon: Database,
    settings: [
      { key: 'neo4j_uri', label: 'Neo4j URI', type: 'text', placeholder: 'bolt://localhost:7687', value: 'bolt://localhost:7687' },
      { key: 'neo4j_user', label: 'Neo4j User', type: 'text', placeholder: 'neo4j', value: 'neo4j' },
      { key: 'neo4j_password', label: 'Neo4j Password', type: 'password', placeholder: '••••••••', value: '' },
      { key: 'qdrant_url', label: 'Qdrant URL', type: 'text', placeholder: 'http://localhost:6333', value: 'http://localhost:6333' },
      { key: 'postgres_url', label: 'PostgreSQL URL', type: 'text', placeholder: 'postgresql+asyncpg://...', value: '' },
    ],
  },
  {
    id: 'web',
    label: 'Web & Extraction',
    icon: Globe,
    settings: [
      { key: 'playwright_headless', label: 'Playwright Headless', type: 'toggle', value: 'true' },
      { key: 'max_concurrent', label: 'Max Concurrent Jobs', type: 'text', placeholder: '3', value: '3' },
    ],
  },
  {
    id: 'api',
    label: 'API Keys',
    icon: Key,
    settings: [
      { key: 'openai_api_key', label: 'OpenAI API Key', type: 'password', placeholder: 'sk-...', value: '' },
      { key: 'openrouter_api_key', label: 'OpenRouter API Key', type: 'password', placeholder: 'sk-or-...', value: '' },
      { key: 'nvidia_api_key', label: 'NVIDIA API Key', type: 'password', placeholder: 'nvapi-...', value: '' },
    ],
  },
]

export default function SettingsPage() {
  const [groups, setGroups] = useState(defaultSettings)
  const [saved, setSaved] = useState(false)

  const updateSetting = (groupId: string, key: string, value: string) => {
    setGroups((prev) =>
      prev.map((g) =>
        g.id === groupId
          ? { ...g, settings: g.settings.map((s) => (s.key === key ? { ...s, value } : s)) }
          : g
      )
    )
    setSaved(false)
  }

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="p-lg max-w-container-max mx-auto">
      <div className="mb-xl flex items-center justify-between">
        <div>
          <h1 className="font-display text-display text-on-surface mb-xs">Settings</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant">
            Configure your InstaGPT GraphRAG engine.
          </p>
        </div>
        <button
          onClick={handleSave}
          className="flex items-center gap-sm bg-primary text-white px-lg py-sm rounded-lg font-label-sm text-label-sm hover:bg-primary/90 transition-colors active:scale-95"
        >
          {saved ? (
            <>
              <CheckCircle size={16} />
              Saved
            </>
          ) : (
            <>
              <Save size={16} />
              Save Settings
            </>
          )}
        </button>
      </div>

      <div className="space-y-lg">
        {groups.map((group) => {
          const Icon = group.icon
          return (
            <div key={group.id} className="layer-1 rounded-xl p-lg">
              <div className="flex items-center gap-sm mb-lg">
                <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center border border-primary/20">
                  <Icon size={16} className="text-primary" />
                </div>
                <h2 className="font-h2 text-h2 text-on-surface">{group.label}</h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                {group.settings.map((setting) => (
                  <div key={setting.key}>
                    <label className="font-label-sm text-label-sm text-on-surface-variant block mb-1">
                      {setting.label}
                    </label>
                    {setting.type === 'toggle' ? (
                      <button
                        onClick={() => updateSetting(group.id, setting.key, setting.value === 'true' ? 'false' : 'true')}
                        className={`relative w-12 h-6 rounded-full transition-colors ${
                          setting.value === 'true' ? 'bg-primary' : 'bg-surface-variant'
                        }`}
                      >
                        <span
                          className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                            setting.value === 'true' ? 'translate-x-6' : 'translate-x-0.5'
                          }`}
                        />
                      </button>
                    ) : setting.type === 'select' ? (
                      <select
                        value={setting.value}
                        onChange={(e) => updateSetting(group.id, setting.key, e.target.value)}
                        className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-md py-sm text-on-background font-body-md focus:border-primary focus:outline-none transition-colors"
                      >
                        {setting.options?.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={setting.type}
                        value={setting.value}
                        onChange={(e) => updateSetting(group.id, setting.key, e.target.value)}
                        placeholder={setting.placeholder}
                        className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-md py-sm text-on-background font-body-md placeholder:text-outline focus:border-primary focus:outline-none transition-colors"
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Danger Zone */}
      <div className="mt-xl border border-red-400/30 rounded-xl p-lg">
        <h2 className="font-h2 text-h2 text-red-400 mb-md">Danger Zone</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-body-md text-body-md text-on-surface">Reset Knowledge Graph</p>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              Permanently delete all entities, relationships, and source data.
            </p>
          </div>
          <button className="bg-red-400/10 text-red-400 border border-red-400/30 px-md py-sm rounded-lg font-label-sm text-label-sm hover:bg-red-400/20 transition-colors">
            Reset All Data
          </button>
        </div>
      </div>
    </div>
  )
}

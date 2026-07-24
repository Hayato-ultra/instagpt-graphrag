import { Outlet, Link, useLocation } from 'react-router-dom'
import { Brain, GitGraph, BookOpen, Search, Menu } from 'lucide-react'
import { useAppStore } from '../store'

const navItems = [
  { path: '/', label: 'Home', icon: Brain },
  { path: '/graph', label: 'Graph', icon: GitGraph },
  { path: '/notebook', label: 'Notebook', icon: BookOpen },
  { path: '/search', label: 'Search', icon: Search },
]

export default function Layout() {
  const location = useLocation()
  const { sidebarOpen, toggleSidebar } = useAppStore()

  return (
    <div className="flex h-screen bg-bg">
      <aside
        className={`${sidebarOpen ? 'w-60' : 'w-16'} bg-surface border-r border-border flex flex-col transition-all duration-200`}
      >
        <div className="p-4 border-b border-border flex items-center gap-3">
          <button onClick={toggleSidebar} className="text-muted hover:text-text">
            <Menu size={20} />
          </button>
          {sidebarOpen && (
            <h1 className="text-lg font-bold text-accent">KG AI</h1>
          )}
        </div>

        <nav className="flex-1 p-2">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                  active
                    ? 'bg-accent/10 text-accent'
                    : 'text-muted hover:text-text hover:bg-surface'
                }`}
              >
                <Icon size={20} />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-border">
          {sidebarOpen && (
            <p className="text-xs text-muted">v1.0.0</p>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}

import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  LineChart,
  GitBranch,
  Search,
  Tag,
  FileText,
  BookOpen,
  Brain,
  Star,
  Settings,
  Menu,
  Bell,
  User,
} from 'lucide-react'
import { useAppStore } from '../store'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/analyze', label: 'Analyze', icon: LineChart },
  { path: '/graph', label: 'Graph', icon: GitBranch },
  { path: '/search', label: 'Search', icon: Search },
  { path: '/entities', label: 'Entities', icon: Tag },
  { path: '/sources', label: 'Sources', icon: FileText },
  { path: '/notebook', label: 'Notebook', icon: BookOpen },
  { path: '/ai-research', label: 'AI Research', icon: Brain },
  { path: '/review', label: 'Review', icon: Star },
]

export default function Layout() {
  const location = useLocation()
  const { sidebarOpen, toggleSidebar } = useAppStore()

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-sidebar-width' : 'w-16'
        } bg-surface-container border-r border-outline-variant flex flex-col transition-all duration-200 fixed left-0 top-0 bottom-0 z-40`}
      >
        {/* Brand */}
        <div className="flex items-center gap-md px-md py-lg border-b border-outline-variant h-16 shrink-0">
          <button onClick={toggleSidebar} className="text-on-surface-variant hover:text-primary transition-colors">
            <Menu size={20} />
          </button>
          {sidebarOpen && (
            <div>
              <h1 className="font-h1 text-h1 text-primary">InstaGPT</h1>
              <p className="font-label-sm text-label-sm text-on-surface-variant">GraphRAG Engine</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-md space-y-xs">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-sm py-2 px-md transition-all duration-200 font-label-sm text-label-sm ${
                  active
                    ? 'bg-primary/10 text-primary border-l-2 border-primary'
                    : 'text-on-surface-variant hover:bg-surface-variant border-l-2 border-transparent'
                }`}
              >
                <Icon size={18} />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            )
          })}
        </nav>

        {/* Bottom */}
        <div className="p-md border-t border-outline-variant">
          <Link
            to="/settings"
            className="flex items-center gap-sm text-on-surface-variant hover:bg-surface-variant transition-all duration-200 font-label-sm text-label-sm py-2 px-2 rounded-lg"
          >
            <Settings size={18} />
            {sidebarOpen && <span>Settings</span>}
          </Link>
        </div>
      </aside>

      {/* Main area */}
      <div className={`flex-1 flex flex-col ${sidebarOpen ? 'ml-sidebar-width' : 'ml-16'} transition-all duration-200`}>
        {/* Top bar */}
        <header className="bg-background border-b border-outline-variant flex justify-between items-center w-full px-md h-16 fixed top-0 z-50" style={{ left: sidebarOpen ? '260px' : '64px', right: 0 }}>
          <div className="flex items-center gap-md">
            <span className="font-h1 text-h1 text-primary hidden md:block">InstaGPT</span>
          </div>

          {/* Search bar */}
          <div className="hidden md:flex items-center w-96 max-w-lg layer-2 rounded-lg px-3 py-1.5 backdrop-blur-md">
            <Search size={16} className="text-outline mr-2" />
            <input
              className="bg-transparent border-none outline-none text-body-md font-body-md text-on-background w-full placeholder:text-outline focus:ring-0 p-0"
              placeholder="Search entities or relationships... (Cmd+K)"
              type="text"
            />
            <div className="flex gap-1">
              <span className="border border-outline-variant rounded px-1 text-[10px] text-outline font-mono">&#8984;</span>
              <span className="border border-outline-variant rounded px-1 text-[10px] text-outline font-mono">K</span>
            </div>
          </div>

          <div className="flex items-center gap-sm text-primary">
            <button className="w-8 h-8 flex items-center justify-center rounded-full text-on-surface-variant hover:text-primary transition-colors hover:bg-surface-variant">
              <Bell size={20} />
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-full text-on-surface-variant hover:text-primary transition-colors hover:bg-surface-variant">
              <User size={20} />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 pt-16 min-h-screen overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

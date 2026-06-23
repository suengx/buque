import { Link } from '@tanstack/react-router'
import { AlertTriangle, BarChart3, LayoutDashboard, MessageSquare } from 'lucide-react'
import ThemeToggle from '#/components/ThemeToggle'

const nav = [
  { to: '/', label: '日报总览', icon: LayoutDashboard },
  { to: '/alerts', label: '风险预警', icon: AlertTriangle },
  { to: '/feedback', label: '人工反馈', icon: MessageSquare },
]

export default function AppSidebar() {
  return (
    <aside className="sidebar-shell fixed inset-y-0 left-0 z-40 flex w-64 flex-col">
      <div className="border-b border-[var(--line)] px-6 py-5">
        <div className="sidebar-brand text-lg font-bold tracking-tight">补雀 BuQue</div>
        <div className="text-xs demo-muted">早一步预警，少一次缺货</div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {nav.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="sidebar-link [&.active]:active"
            activeProps={{ className: 'sidebar-link active' }}
          >
            <Icon size={18} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="space-y-3 border-t border-[var(--line)] px-4 py-4">
        <ThemeToggle />
        <div className="text-xs demo-muted">
          <BarChart3 size={14} className="mb-2 inline" /> Planning Monitor
        </div>
      </div>
    </aside>
  )
}

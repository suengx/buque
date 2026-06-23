import { Link } from '@tanstack/react-router'
import { AlertTriangle, LayoutDashboard, MessageSquare } from 'lucide-react'

const nav = [
  { to: '/', label: '日报总览', icon: LayoutDashboard },
  { to: '/alerts', label: '风险预警', icon: AlertTriangle },
  { to: '/feedback', label: '人工反馈', icon: MessageSquare },
]

export default function AppSidebar() {
  return (
    <aside className="sidebar-shell sidebar-shell-dark fixed inset-y-0 left-0 z-40 flex w-60 flex-col">
      <div className="sidebar-brand-block">
        <img src="/brand-mascot.png" alt="" className="sidebar-brand-mascot" />
        <div className="min-w-0 flex-1">
          <div className="sidebar-brand text-[15px] font-semibold leading-tight">补雀 BuQue</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {nav.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="sidebar-link [&.active]:active"
            activeProps={{ className: 'sidebar-link active' }}
          >
            <Icon size={16} strokeWidth={2} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="sidebar-footer-minimal">计划监控</div>
    </aside>
  )
}

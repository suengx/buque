import { Link } from '@tanstack/react-router'
import { AlertTriangle, BarChart3, LayoutDashboard, MessageSquare } from 'lucide-react'

const nav = [
  { to: '/', label: '日报总览', icon: LayoutDashboard },
  { to: '/alerts', label: '风险预警', icon: AlertTriangle },
  { to: '/feedback', label: '人工反馈', icon: MessageSquare },
]

export default function AppSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-white/10 bg-[#17262B] text-white">
      <div className="border-b border-white/10 px-6 py-5">
        <div className="text-lg font-bold tracking-tight">补雀 BuQue</div>
        <div className="text-xs text-white/60">早一步预警，少一次缺货</div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {nav.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-white/75 transition hover:bg-white/10 [&.active]:bg-[#0FA58A]/20 [&.active]:text-white"
          >
            <Icon size={18} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="border-t border-white/10 px-6 py-4 text-xs text-white/50">
        <BarChart3 size={14} className="mb-2 inline" /> Planning Monitor
      </div>
    </aside>
  )
}

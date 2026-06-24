import { Link, useNavigate } from '@tanstack/react-router'
import { AlertTriangle, Bot, LayoutDashboard, LogOut, MessageSquare, Sliders } from 'lucide-react'
import { useAuth } from '#/context/AuthContext'
import { useSnapshot } from '#/context/SnapshotContext'

const nav = [
  { to: '/', label: '日报总览', icon: LayoutDashboard },
  { to: '/alerts', label: '风险预警', icon: AlertTriangle },
  { to: '/chat', label: '监控助手', icon: Bot },
  { to: '/feedback', label: '人工反馈', icon: MessageSquare },
  { to: '/settings/rules', label: '规则配置', icon: Sliders },
]

export default function AppSidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { selectedSnapshotId } = useSnapshot()

  const displayName = user?.display_name || user?.email || '用户'

  const handleLogout = () => {
    logout()
    void navigate({ to: '/login' })
  }

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
            search={to === '/chat' && selectedSnapshotId ? { snapshot_id: selectedSnapshotId } : undefined}
            className="sidebar-link [&.active]:active"
            activeProps={{ className: 'sidebar-link active' }}
          >
            <Icon size={16} strokeWidth={2} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="sidebar-user-block">
        <div className="sidebar-user-meta">
          <div className="sidebar-user-name">{displayName}</div>
          {user?.email && user.display_name ? (
            <div className="sidebar-user-email">{user.email}</div>
          ) : null}
        </div>
        <button type="button" className="sidebar-logout" onClick={handleLogout}>
          <LogOut size={14} strokeWidth={2} />
          退出
        </button>
      </div>
    </aside>
  )
}

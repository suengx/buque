import { Link, useNavigate } from '@tanstack/react-router'
import {
  AlertTriangle,
  Bot,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  PanelLeft,
  PanelLeftClose,
  Sliders,
} from 'lucide-react'
import { useAuth } from '#/context/AuthContext'
import { useSidebarLayout } from '#/context/SidebarLayoutContext'
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
  const { collapsed, toggleCollapsed } = useSidebarLayout()

  const displayName = user?.display_name || user?.email || '用户'
  const initial = displayName.charAt(0).toUpperCase()

  const handleLogout = () => {
    logout()
    void navigate({ to: '/login' })
  }

  return (
    <aside
      className="sidebar-shell sidebar-shell-dark app-sidebar"
      data-collapsed={collapsed ? 'true' : undefined}
    >
      <div className="sidebar-brand-block">
        {!collapsed ? (
          <>
            <img src="/brand-mascot.png" alt="" className="sidebar-brand-mascot" />
            <div className="min-w-0 flex-1">
              <div className="sidebar-brand text-[15px] font-semibold leading-tight">
                补雀 BuQue
              </div>
            </div>
          </>
        ) : (
          <img src="/brand-mascot.png" alt="补雀 BuQue" className="sidebar-brand-mascot" />
        )}
        <button
          type="button"
          className="sidebar-collapse-btn"
          aria-label={collapsed ? '展开侧栏' : '折叠侧栏'}
          onClick={toggleCollapsed}
        >
          {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>
      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {nav.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            search={to === '/chat' && selectedSnapshotId ? { snapshot_id: selectedSnapshotId } : undefined}
            className="sidebar-link [&.active]:active"
            activeProps={{ className: 'sidebar-link active' }}
            title={collapsed ? label : undefined}
          >
            <Icon size={16} strokeWidth={2} />
            {!collapsed ? <span className="sidebar-link-label">{label}</span> : null}
          </Link>
        ))}
      </nav>
      <div className="sidebar-user-block">
        {!collapsed ? (
          <>
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
          </>
        ) : (
          <div className="sidebar-user-collapsed">
            <span className="sidebar-user-avatar" title={displayName}>
              {initial}
            </span>
            <button
              type="button"
              className="sidebar-logout sidebar-logout-icon"
              aria-label="退出"
              onClick={handleLogout}
            >
              <LogOut size={14} strokeWidth={2} />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}

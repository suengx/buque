import type { LucideIcon } from 'lucide-react'
import { cn } from '#/lib/utils'

type Props = {
  /** 概览 / 专项类卡片左上角标题 */
  title?: string
  /** 风险等级类卡片右上角「标签 + 图标」融合展示，如「高风险」 */
  badge?: string
  value: string | number
  percent?: string
  /** 卡片内浅色说明，替代 tooltip */
  description?: string
  icon?: LucideIcon
  iconClassName?: string
  accent?: 'red' | 'orange' | 'yellow' | 'green' | 'neutral'
  onClick?: () => void
}

const accentBorder: Record<NonNullable<Props['accent']>, string> = {
  red: 'border-l-[var(--risk-red-border)]',
  orange: 'border-l-[var(--risk-orange-border)]',
  yellow: 'border-l-[var(--risk-yellow-border)]',
  green: 'border-l-[var(--risk-green-border)]',
  neutral: 'border-l-[var(--hairline-strong)]',
}

const badgeAccent: Record<NonNullable<Props['accent']>, string> = {
  red: 'buque-metric-badge-red',
  orange: 'buque-metric-badge-orange',
  yellow: 'buque-metric-badge-yellow',
  green: 'buque-metric-badge-green',
  neutral: 'buque-metric-badge-neutral',
}

const iconAccentBg: Record<NonNullable<Props['accent']>, string> = {
  red: 'bg-[var(--risk-red-bg)] text-[var(--risk-red-chart)]',
  orange: 'bg-[var(--risk-orange-bg)] text-[var(--risk-orange-chart)]',
  yellow: 'bg-[var(--risk-yellow-bg)] text-[var(--risk-yellow-chart)]',
  green: 'bg-[var(--risk-green-bg)] text-[var(--risk-green-chart)]',
  neutral: 'bg-[color-mix(in_oklab,var(--aqua)_12%,transparent)] text-[var(--aqua)]',
}

const percentAccent: Record<NonNullable<Props['accent']>, string> = {
  red: 'text-[var(--risk-red-text)]',
  orange: 'text-[var(--risk-orange-text)]',
  yellow: 'text-[var(--risk-yellow-text)]',
  green: 'text-[var(--risk-green-text)]',
  neutral: 'text-[var(--aqua)]',
}

export function MetricCard({
  title,
  badge,
  value,
  percent,
  description,
  icon: Icon,
  iconClassName,
  accent = 'neutral',
  onClick,
}: Props) {
  const clickable = Boolean(onClick)
  const showBadge = Boolean(badge && Icon)
  const showIconOnly = Boolean(Icon && title && !badge)

  return (
    <div
      className={cn(
        'buque-metric border-l-4',
        accentBorder[accent],
        clickable && 'buque-metric-clickable',
      )}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') onClick?.()
            }
          : undefined
      }
    >
      <div className="flex items-start justify-between gap-3">
        {title ? <div className="buque-metric-title">{title}</div> : <span aria-hidden />}
        {showBadge ? (
          <div className={cn('buque-metric-badge', badgeAccent[accent])}>
            <Icon size={15} strokeWidth={2.25} />
            <span>{badge}</span>
          </div>
        ) : showIconOnly ? (
          <div className={cn('buque-metric-icon-wrap', iconAccentBg[accent], iconClassName)}>
            <Icon size={18} strokeWidth={2.25} />
          </div>
        ) : null}
      </div>
      <div className="buque-metric-value">{value}</div>
      {percent ? (
        <div className={cn('buque-metric-percent', percentAccent[accent])}>{percent}</div>
      ) : null}
      {description ? <p className="buque-metric-desc">{description}</p> : null}
    </div>
  )
}

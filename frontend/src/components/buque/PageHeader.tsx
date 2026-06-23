import { Info } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '#/lib/utils'

export function PageHeader({
  title,
  subtitle,
  tooltip,
  actions,
  className,
}: {
  title: string
  subtitle?: string
  tooltip?: string
  actions?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('buque-page-header', className)}>
      <div className={cn(actions && 'flex-1')}>
        <div className="flex items-center gap-2">
          <h1 className="buque-page-title">{title}</h1>
          {tooltip ? (
            <span className="buque-tooltip-wrap text-[var(--sea-ink-soft)]">
              <Info size={16} />
              <span className="buque-tooltip">{tooltip}</span>
            </span>
          ) : null}
        </div>
        {subtitle ? <p className="buque-page-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  )
}

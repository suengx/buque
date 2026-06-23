import type { ReactNode } from 'react'
import { cn } from '#/lib/utils'

export function ChartCard({
  title,
  subtitle,
  children,
  className,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('buque-panel-flat', className)}>
      <div className="mb-2">
        <h3 className="buque-distribution-chart-title">{title}</h3>
        {subtitle ? <p className="buque-distribution-chart-subtitle">{subtitle}</p> : null}
      </div>
      {children}
    </div>
  )
}

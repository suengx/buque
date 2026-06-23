import { cn } from '#/lib/utils'

const levelClass: Record<string, string> = {
  RED: 'risk-badge-red',
  ORANGE: 'risk-badge-orange',
  YELLOW: 'risk-badge-yellow',
  GREEN: 'risk-badge-green',
}

const levelLabel: Record<string, string> = {
  RED: '红灯',
  ORANGE: '橙灯',
  YELLOW: '黄灯',
  GREEN: '绿灯',
}

export function RiskBadge({ level }: { level: string }) {
  return (
    <span className={cn('risk-badge', levelClass[level] ?? 'risk-badge-yellow')}>
      {levelLabel[level] ?? level}
    </span>
  )
}

export function GlassCard({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn('buque-panel-flat', className)}>{children}</div>
}

export function StatCard({
  title,
  value,
  hint,
}: {
  title: string
  value: string | number
  hint?: string
}) {
  return (
    <GlassCard>
      <div className="text-sm demo-muted">{title}</div>
      <div className="mt-2 text-3xl font-bold text-[var(--sea-ink)]">{value}</div>
      {hint ? <div className="mt-1 text-xs demo-muted">{hint}</div> : null}
    </GlassCard>
  )
}

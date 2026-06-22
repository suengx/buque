import { cn } from '#/lib/utils'

const levelStyles: Record<string, string> = {
  RED: 'bg-red-100 text-red-700 border-red-200',
  ORANGE: 'bg-orange-100 text-orange-700 border-orange-200',
  YELLOW: 'bg-amber-100 text-amber-800 border-amber-200',
  GREEN: 'bg-emerald-100 text-emerald-700 border-emerald-200',
}

const levelLabel: Record<string, string> = {
  RED: '红灯',
  ORANGE: '橙灯',
  YELLOW: '黄灯',
  GREEN: '绿灯',
}

export function RiskBadge({ level }: { level: string }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        levelStyles[level] ?? 'bg-slate-100 text-slate-700',
      )}
    >
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
  return (
    <div
      className={cn(
        'rounded-2xl border border-white/30 bg-white/70 p-5 shadow-lg backdrop-blur-xl',
        className,
      )}
    >
      {children}
    </div>
  )
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
      <div className="text-sm text-[#45515A]">{title}</div>
      <div className="mt-2 text-3xl font-bold text-[#0B3D3A]">{value}</div>
      {hint ? <div className="mt-1 text-xs text-[#45515A]/80">{hint}</div> : null}
    </GlassCard>
  )
}

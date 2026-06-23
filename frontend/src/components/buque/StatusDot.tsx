import { HANDLING_STATUS_LABEL, HANDLING_STATUS_TONE } from '#/lib/labels'
import { cn } from '#/lib/utils'

const dotClass: Record<string, string> = {
  danger: 'bg-[var(--risk-red-text)]',
  warning: 'bg-[var(--risk-orange-text)]',
  success: 'bg-[var(--status-success)]',
}

export function StatusDot({ status }: { status: string }) {
  const tone = HANDLING_STATUS_TONE[status] ?? 'danger'
  const label = HANDLING_STATUS_LABEL[status] ?? status
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span className={cn('h-2 w-2 shrink-0 rounded-full', dotClass[tone])} />
      <span>{label}</span>
    </span>
  )
}

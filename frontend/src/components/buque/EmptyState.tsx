import { Inbox } from 'lucide-react'

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <div className="buque-empty">
      <Inbox size={40} strokeWidth={1.25} className="opacity-40" />
      <div className="text-sm font-medium text-[var(--sea-ink)]">{title}</div>
      {description ? <p className="max-w-sm text-xs">{description}</p> : null}
      {action}
    </div>
  )
}

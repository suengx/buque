import { cn } from '#/lib/utils'

export function RuleEnableStatus({ enabled }: { enabled: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span
        className={cn(
          'h-2 w-2 shrink-0 rounded-full',
          enabled ? 'bg-[var(--status-success)]' : 'bg-[var(--sea-ink-soft)]',
        )}
      />
      <span>{enabled ? '已启用' : '已停用'}</span>
    </span>
  )
}

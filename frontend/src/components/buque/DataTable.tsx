import type { ReactNode } from 'react'
import { cn } from '#/lib/utils'
import { EmptyState } from '#/components/buque/EmptyState'

export function DataTable({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('demo-table-shell overflow-x-auto', className)}>
      <table className="demo-table w-full">{children}</table>
    </div>
  )
}

export function DataTableEmpty({ title, description }: { title: string; description?: string }) {
  return (
    <tr>
      <td colSpan={99}>
        <EmptyState title={title} description={description} />
      </td>
    </tr>
  )
}

import type { ReactNode } from 'react'
import { cn } from '#/lib/utils'

export function SectionBlock({
  label,
  description,
  children,
  className,
}: {
  label: string
  description?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('buque-section-block', className)}>
      <div className="buque-section-heading">
        <h2 className="buque-section-title">{label}</h2>
        {description ? <p className="buque-section-desc">{description}</p> : null}
      </div>
      {children}
    </section>
  )
}

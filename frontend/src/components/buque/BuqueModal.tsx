import { useEffect, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '#/lib/utils'

type Props = {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  className?: string
}

export function BuqueModal({ open, title, onClose, children, className }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="buque-modal-root" role="presentation" onClick={onClose}>
      <div
        className={cn('buque-modal-panel', className)}
        role="dialog"
        aria-modal="true"
        aria-labelledby="buque-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="buque-modal-header">
          <h3 id="buque-modal-title" className="buque-modal-title">
            {title}
          </h3>
          <button type="button" className="buque-modal-close" aria-label="关闭" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <div className="buque-modal-body">{children}</div>
      </div>
    </div>
  )
}

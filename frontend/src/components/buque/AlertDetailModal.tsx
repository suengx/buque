import { BuqueModal } from '#/components/buque/BuqueModal'
import { SkuAlertDetailContent } from '#/components/buque/SkuAlertDetailContent'

export type AlertDetailTarget = {
  sku: string
  warehouse?: string
  productName?: string | null
}

type Props = {
  target: AlertDetailTarget | null
  onClose: () => void
}

export function AlertDetailModal({ target, onClose }: Props) {
  const title = target
    ? `${target.sku}${target.productName ? ` · ${target.productName}` : ''}`
    : '风险详情'

  return (
    <BuqueModal
      open={target !== null}
      title={title}
      onClose={onClose}
      className="buque-modal-panel-lg"
    >
      {target ? <SkuAlertDetailContent sku={target.sku} warehouse={target.warehouse} /> : null}
    </BuqueModal>
  )
}

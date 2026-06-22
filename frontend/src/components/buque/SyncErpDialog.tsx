import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, queryKeys, type ErpSyncStatusResponse } from '#/lib/api'
import { GlassCard } from '#/components/buque/RiskBadge'

type Props = {
  open: boolean
  onClose: () => void
  monitorDate?: string
}

function SourceRow({ item }: { item: ErpSyncStatusResponse['sources'][number] }) {
  const label =
    item.source === 'erp_inventory'
      ? '产品库存'
      : item.source === 'erp_orders'
        ? '全渠道订单'
        : 'TMS 在途'
  const statusColor =
    item.status === 'SUCCESS'
      ? 'text-emerald-700'
      : item.status === 'FAILED'
        ? 'text-red-600'
        : item.status === 'RUNNING'
          ? 'text-amber-700'
          : 'text-[#45515A]'
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/40 py-2 text-sm last:border-0">
      <div>
        <div className="font-medium text-[#0B3D3A]">{label}</div>
        <div className={`${statusColor}`}>
          {item.status}
          {item.status === 'SUCCESS' ? ` · ${item.row_count} 行` : ''}
        </div>
        {item.error ? <div className="mt-1 text-xs text-red-600">{item.error}</div> : null}
      </div>
    </div>
  )
}

export function SyncErpDialog({ open, onClose, monitorDate }: Props) {
  const qc = useQueryClient()
  const [status, setStatus] = useState<ErpSyncStatusResponse | null>(null)
  const [polling, setPolling] = useState(false)

  const syncMutation = useMutation({
    mutationFn: (runPipeline: boolean) => api.startErpSync({ monitorDate, runPipeline }),
    onSuccess: () => {
      setPolling(true)
    },
  })

  useEffect(() => {
    if (!polling) return
    let cancelled = false
    const tick = async () => {
      try {
        const s = await api.getErpSyncStatus(monitorDate)
        if (cancelled) return
        setStatus(s)
        if (!s.running) {
          setPolling(false)
          await qc.invalidateQueries({ queryKey: queryKeys.dailyReport(monitorDate) })
          await qc.invalidateQueries({ queryKey: ['alerts'] })
        }
      } catch {
        if (!cancelled) setPolling(false)
      }
    }
    tick()
    const id = window.setInterval(tick, 2000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [polling, monitorDate, qc])

  if (!open) return null

  const busy = syncMutation.isPending || polling

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <GlassCard className="w-full max-w-lg">
        <h2 className="text-lg font-semibold text-[#0B3D3A]">同步 ERP 数据</h2>
        <p className="mt-2 text-sm text-[#45515A]">
          将登录积加 ERP 并拉取产品库存、全渠道订单（近 30 天）与 TMS 在途数据，预计需要数分钟。
        </p>
        {syncMutation.error ? (
          <div className="demo-alert-danger mt-3 text-sm">{String(syncMutation.error.message)}</div>
        ) : null}
        {status ? (
          <div className="mt-4 rounded-xl bg-white/50 p-3">
            {status.sources.map((s) => (
              <SourceRow key={s.source} item={s} />
            ))}
          </div>
        ) : null}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button type="button" className="demo-button-secondary" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="demo-button-secondary"
            disabled={busy}
            onClick={() => syncMutation.mutate(false)}
          >
            {busy && !syncMutation.variables ? '同步中...' : '仅同步'}
          </button>
          <button
            type="button"
            className="demo-button"
            disabled={busy}
            onClick={() => syncMutation.mutate(true)}
          >
            {busy ? '处理中...' : '同步并分析'}
          </button>
        </div>
      </GlassCard>
    </div>
  )
}

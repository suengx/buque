import type { MonitorResult, PaginatedAlerts } from '#/lib/api'
import { riskTypeLabel } from '#/lib/labels'
import { EmptyState } from '#/components/buque/EmptyState'
import { RiskBadge } from '#/components/buque/RiskBadge'
import { StatusDot } from '#/components/buque/StatusDot'
import type { AlertDetailTarget } from '#/components/buque/AlertDetailModal'

type Props = {
  data: PaginatedAlerts | undefined
  isLoading: boolean
  error: Error | null
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onViewDetail: (target: AlertDetailTarget) => void
}

function formatDos(dos: string | null) {
  if (!dos) return '—'
  const n = Number(dos)
  return Number.isFinite(n) ? n.toFixed(1) : dos
}

export function AlertsTable({
  data,
  isLoading,
  error,
  currentPage,
  totalPages,
  onPageChange,
  onViewDetail,
}: Props) {
  return (
    <section className="buque-table-panel min-w-0">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--sea-ink)]">风险预警列表</h2>
        <span className="text-xs text-[var(--sea-ink-soft)]">共 {data?.total ?? 0} 条</span>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-sm text-[var(--sea-ink-soft)]">加载中...</div>
      ) : error ? (
        <div className="py-12 text-center text-sm text-[var(--status-danger)]">无法加载风险清单。</div>
      ) : (
        <>
          <div className="buque-alerts-table-wrap">
            <table className="buque-alerts-table">
              <thead>
                <tr>
                  <th>监控日</th>
                  <th>关联对象</th>
                  <th>风险类型</th>
                  <th>风险等级</th>
                  <th>风险描述</th>
                  <th>DOS</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {!data?.items.length ? (
                  <tr>
                    <td colSpan={8}>
                      <EmptyState title="无匹配预警" description="调整筛选条件或先运行分析。" />
                    </td>
                  </tr>
                ) : (
                  data.items.map((row: MonitorResult) => (
                    <AlertRow key={row.id} row={row} onViewDetail={onViewDetail} />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {data && data.total > 0 ? (
            <div className="mt-3 flex items-center justify-end gap-2 text-sm">
              <button
                type="button"
                className="demo-button demo-button-secondary demo-button-sm"
                disabled={currentPage <= 1}
                onClick={() => onPageChange(currentPage - 1)}
              >
                上一页
              </button>
              <span className="text-xs text-[var(--sea-ink-soft)]">
                第 {currentPage} / {totalPages} 页
              </span>
              <button
                type="button"
                className="demo-button demo-button-secondary demo-button-sm"
                disabled={currentPage >= totalPages}
                onClick={() => onPageChange(currentPage + 1)}
              >
                下一页
              </button>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}

function AlertRow({
  row,
  onViewDetail,
}: {
  row: MonitorResult
  onViewDetail: (target: AlertDetailTarget) => void
}) {
  const openDetail = () =>
    onViewDetail({
      sku: row.sku,
      warehouse: row.warehouse ?? undefined,
      productName: row.product_name,
    })

  return (
    <tr className="buque-alerts-row-clickable" onClick={openDetail}>
      <td className="whitespace-nowrap text-xs text-[var(--sea-ink-soft)]">{row.date}</td>
      <td className="min-w-[140px]">
        <div className="font-medium text-[var(--sea-ink)]">{row.sku}</div>
        <div className="mt-0.5 text-xs text-[var(--sea-ink-soft)]">{row.product_name ?? '—'}</div>
        {row.warehouse ? (
          <div className="mt-0.5 text-xs text-[var(--aqua)]">{row.warehouse}</div>
        ) : null}
      </td>
      <td className="whitespace-nowrap text-sm">{riskTypeLabel(row.risk_type)}</td>
      <td>
        <RiskBadge level={row.risk_level} />
      </td>
      <td className="max-w-[220px] text-sm leading-snug">
        <span className="line-clamp-2">{row.primary_explanation ?? '—'}</span>
      </td>
      <td className="whitespace-nowrap font-medium">{formatDos(row.dos)}</td>
      <td>
        <StatusDot status={row.handling_status} />
      </td>
      <td className="whitespace-nowrap">
        <button
          type="button"
          className="text-sm font-medium text-[var(--aqua)]"
          onClick={(e) => {
            e.stopPropagation()
            openDetail()
          }}
        >
          查看详情
        </button>
      </td>
    </tr>
  )
}

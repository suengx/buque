import { createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, queryKeys } from '#/lib/api'
import { riskTypeLabel } from '#/lib/labels'
import { useSnapshot } from '#/context/SnapshotContext'
import { MetricCard } from '#/components/buque/MetricCard'
import { PageHeader } from '#/components/buque/PageHeader'

type FeedbackSearch = {
  sku?: string
  risk_type?: string
}

export const Route = createFileRoute('/_app/feedback/')({
  validateSearch: (search: Record<string, unknown>): FeedbackSearch => ({
    sku: (search.sku as string) || undefined,
    risk_type: (search.risk_type as string) || undefined,
  }),
  component: FeedbackPage,
})

function FeedbackPage() {
  const search = Route.useSearch()
  const { selectedSnapshotId } = useSnapshot()
  const qc = useQueryClient()
  const { data: stats } = useQuery({
    queryKey: queryKeys.feedbackStats,
    queryFn: () => api.feedbackStats(),
  })
  const [sku, setSku] = useState(search.sku ?? '')
  const [riskType, setRiskType] = useState(search.risk_type ?? 'STOCKOUT')
  const [decision, setDecision] = useState('ADOPTED')
  const [remark, setRemark] = useState('')

  useEffect(() => {
    if (search.sku) setSku(search.sku)
    if (search.risk_type) setRiskType(search.risk_type)
  }, [search.sku, search.risk_type])

  const mutation = useMutation({
    mutationFn: () =>
      api.createFeedback({
        date: new Date().toISOString().slice(0, 10),
        sku,
        risk_type: riskType,
        decision,
        remark,
        snapshot_id: selectedSnapshotId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.feedbackStats })
      setRemark('')
    },
  })

  return (
    <div className="buque-page-stack">
      <PageHeader
        title="人工反馈"
        subtitle="记录采纳、驳回与部分采纳"
        tooltip="反馈用于二期学习闭环；一期留痕即可。"
      />

      <div className="buque-metric-grid buque-metric-grid-4">
        <MetricCard title="反馈总数" value={stats?.total ?? 0} accent="neutral" />
        <MetricCard title="采纳" value={stats?.adopted ?? 0} accent="green" />
        <MetricCard title="驳回" value={stats?.rejected ?? 0} accent="red" />
        <MetricCard
          title="采纳率"
          value={`${((stats?.adoption_rate ?? 0) * 100).toFixed(1)}%`}
          accent="neutral"
        />
      </div>

      <div className="buque-panel-flat max-w-lg space-y-4">
        <h2 className="text-base font-semibold text-[var(--sea-ink)]">提交反馈</h2>
        <input
          className="demo-input"
          placeholder="SKU"
          value={sku}
          onChange={(e) => setSku(e.target.value)}
        />
        <select className="demo-select" value={riskType} onChange={(e) => setRiskType(e.target.value)}>
          <option value="STOCKOUT">断货风险</option>
          <option value="SLOW_MOVING">滞销风险</option>
          <option value="SALES_ANOMALY">销量异常</option>
        </select>
        <select className="demo-select" value={decision} onChange={(e) => setDecision(e.target.value)}>
          <option value="ADOPTED">采纳</option>
          <option value="REJECTED">驳回</option>
          <option value="PARTIAL">部分采纳</option>
        </select>
        <textarea
          className="demo-textarea"
          placeholder="备注 / 修正原因"
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
        />
        <button
          className="demo-button"
          disabled={!sku || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          提交反馈
        </button>
        {sku ? (
          <p className="text-xs text-[var(--sea-ink-soft)]">
            当前：{sku} · {riskTypeLabel(riskType)}
          </p>
        ) : null}
      </div>
    </div>
  )
}

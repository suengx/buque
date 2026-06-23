import { createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, queryKeys } from '#/lib/api'
import { GlassCard, StatCard } from '#/components/buque/RiskBadge'

export const Route = createFileRoute('/feedback/')({
  component: FeedbackPage,
})

function FeedbackPage() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({
    queryKey: queryKeys.feedbackStats,
    queryFn: () => api.feedbackStats(),
  })
  const [sku, setSku] = useState('')
  const [riskType, setRiskType] = useState('STOCKOUT')
  const [decision, setDecision] = useState('ADOPTED')
  const [remark, setRemark] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      api.createFeedback({
        date: new Date().toISOString().slice(0, 10),
        sku,
        risk_type: riskType,
        decision,
        remark,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.feedbackStats })
      setRemark('')
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="demo-title text-2xl">人工反馈</h1>
        <p className="text-sm demo-muted">记录采纳 / 驳回 / 部分采纳</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-4">
        <StatCard title="反馈总数" value={stats?.total ?? 0} />
        <StatCard title="采纳" value={stats?.adopted ?? 0} />
        <StatCard title="驳回" value={stats?.rejected ?? 0} />
        <StatCard title="采纳率" value={`${((stats?.adoption_rate ?? 0) * 100).toFixed(1)}%`} />
      </div>
      <GlassCard className="max-w-xl space-y-4">
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
      </GlassCard>
    </div>
  )
}

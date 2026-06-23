import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, queryKeys } from '#/lib/api'
import { GlassCard, RiskBadge } from '#/components/buque/RiskBadge'

export const Route = createFileRoute('/alerts/$skuId')({
  validateSearch: (search: Record<string, unknown>) => ({
    warehouse: (search.warehouse as string | undefined) ?? undefined,
  }),
  component: SkuDetailPage,
})

function SkuDetailPage() {
  const { skuId } = Route.useParams()
  const { warehouse } = Route.useSearch()
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.skuDetail(skuId, warehouse),
    queryFn: () => api.skuDetail(skuId, warehouse),
  })

  if (isLoading) return <div className="p-8 demo-muted">加载 SKU 分析卡...</div>
  if (error) return <div className="p-8 text-[var(--status-danger)]">无法加载 SKU 详情。</div>
  if (!data) return null

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="demo-title text-2xl">{data.sku}</h1>
          <p className="text-sm demo-muted">
            {data.product_name} · {data.warehouse ?? '全仓'}
          </p>
        </div>
        <RiskBadge level={data.risk_level} />
      </div>
      <GlassCard>
        <h2 className="demo-section-title mb-3">风险结论</h2>
        <p className="text-sm">
          {data.risk_type} · DOS {data.dos ?? '-'}
        </p>
        <pre className="demo-code-block mt-3 overflow-x-auto text-xs">
          {JSON.stringify(data.trigger_metrics, null, 2)}
        </pre>
      </GlassCard>
      <GlassCard>
        <h2 className="demo-section-title mb-3">Agent 解释</h2>
        <p className="font-medium text-[var(--sea-ink)]">{data.primary_explanation}</p>
        {data.secondary_explanation ? (
          <p className="mt-2 text-sm demo-muted">次解释：{data.secondary_explanation}</p>
        ) : null}
        {data.tertiary_explanation ? (
          <p className="mt-1 text-sm demo-muted">第三解释：{data.tertiary_explanation}</p>
        ) : null}
        <ul className="mt-3 list-disc pl-5 text-sm">
          {data.key_evidence?.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </GlassCard>
      <GlassCard>
        <h2 className="demo-section-title mb-3">建议动作</h2>
        <p className="text-[var(--sea-ink)]">{data.suggested_action}</p>
        <p className="mt-2 text-sm demo-muted">
          责任：{data.responsible_role} · 时效：{data.action_deadline}
        </p>
        {data.require_human_confirm ? (
          <p className="mt-2 text-sm font-semibold text-[var(--amber)]">须人工确认</p>
        ) : null}
      </GlassCard>
    </div>
  )
}

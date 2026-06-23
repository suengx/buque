import { Link, createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, MessageSquarePlus } from 'lucide-react'
import { api, queryKeys } from '#/lib/api'
import { riskTypeLabel } from '#/lib/labels'
import { GlassCard, RiskBadge } from '#/components/buque/RiskBadge'
import { PageHeader } from '#/components/buque/PageHeader'

export const Route = createFileRoute('/alerts/$skuId')({
  validateSearch: (search: Record<string, unknown>) => ({
    warehouse: (search.warehouse as string | undefined) ?? undefined,
  }),
  component: SkuDetailPage,
})

function formatMetrics(metrics: Record<string, unknown>) {
  return Object.entries(metrics).map(([k, v]) => `${k}: ${String(v)}`)
}

function SkuDetailPage() {
  const { skuId } = Route.useParams()
  const { warehouse } = Route.useSearch()
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.skuDetail(skuId, warehouse),
    queryFn: () => api.skuDetail(skuId, warehouse),
  })

  const agentExplain = useMutation({
    mutationFn: () =>
      api.agentExplainSku(skuId, {
        warehouse,
        monitorDate: data?.monitor_date,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skuDetail(skuId, warehouse) })
    },
  })

  if (isLoading) return <div className="demo-muted">加载 SKU 分析卡...</div>
  if (error) return <div className="text-[var(--status-danger)]">无法加载 SKU 详情。</div>
  if (!data) return null

  const explain = agentExplain.data
  const metrics = formatMetrics(data.trigger_metrics)

  return (
    <div className="space-y-6">
      <Link to="/alerts" className="inline-flex items-center gap-1 text-sm text-[var(--aqua)] no-underline hover:underline">
        <ArrowLeft size={16} />
        返回风险清单
      </Link>

      <PageHeader
        title={data.sku}
        subtitle={`${data.product_name ?? '—'} · ${data.warehouse ?? '全仓'} · ${riskTypeLabel(data.risk_type)}`}
        actions={
          <>
            <RiskBadge level={data.risk_level} />
            <button
              type="button"
              className="demo-button"
              disabled={agentExplain.isPending}
              onClick={() => agentExplain.mutate()}
            >
              {agentExplain.isPending ? 'Agent 分析中…' : 'Agent 深度分析'}
            </button>
            <Link
              to="/feedback"
              search={{
                sku: data.sku,
                risk_type: data.risk_type,
              }}
              className="demo-button demo-button-secondary no-underline"
            >
              <MessageSquarePlus size={16} />
              提交反馈
            </Link>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <GlassCard>
            <h2 className="demo-section-title mb-3">风险结论</h2>
            <p className="text-sm">
              {riskTypeLabel(data.risk_type)} · DOS {data.dos ?? '—'}
            </p>
          </GlassCard>

          <GlassCard>
            <h2 className="demo-section-title mb-3">触发证据</h2>
            <ul className="space-y-1 text-sm">
              {metrics.length ? metrics.map((m) => <li key={m}>{m}</li>) : <li className="demo-muted">无触发指标</li>}
            </ul>
          </GlassCard>

          <GlassCard>
            <h2 className="demo-section-title mb-3">解释</h2>
            {agentExplain.error ? (
              <p className="mb-2 text-sm text-[var(--status-danger)]">
                深度分析失败：{(agentExplain.error as Error).message}
              </p>
            ) : null}
            <p className="font-medium text-[var(--sea-ink)]">
              {explain?.primary_explanation ?? data.primary_explanation ?? '—'}
            </p>
            {(explain?.secondary_explanation ?? data.secondary_explanation) ? (
              <p className="mt-2 text-sm demo-muted">
                次解释：{explain?.secondary_explanation ?? data.secondary_explanation}
              </p>
            ) : null}
            {(explain?.tertiary_explanation ?? data.tertiary_explanation) ? (
              <p className="mt-1 text-sm demo-muted">
                第三解释：{explain?.tertiary_explanation ?? data.tertiary_explanation}
              </p>
            ) : null}
            {explain?.confidence_note ? (
              <p className="mt-2 text-xs demo-muted">{explain.confidence_note}</p>
            ) : null}
            <ul className="mt-3 list-disc pl-5 text-sm">
              {(explain?.key_evidence ?? data.key_evidence)?.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </GlassCard>

          <GlassCard>
            <h2 className="demo-section-title mb-3">建议动作</h2>
            <p className="text-[var(--sea-ink)]">{explain?.suggested_action ?? data.suggested_action ?? '—'}</p>
          </GlassCard>
        </div>

        <div className="space-y-4">
          <GlassCard>
            <h2 className="demo-section-title mb-3">处理信息</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="demo-muted">责任角色</dt>
                <dd>{explain?.responsible_role ?? data.responsible_role ?? '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="demo-muted">建议时效</dt>
                <dd>{explain?.action_deadline ?? data.action_deadline ?? '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="demo-muted">须人工确认</dt>
                <dd>{(explain?.require_human_confirm ?? data.require_human_confirm) ? '是' : '否'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="demo-muted">监控日期</dt>
                <dd>{data.monitor_date}</dd>
              </div>
            </dl>
          </GlassCard>
        </div>
      </div>
    </div>
  )
}

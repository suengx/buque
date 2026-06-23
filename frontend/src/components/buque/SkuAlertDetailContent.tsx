import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquarePlus } from 'lucide-react'
import { api, queryKeys } from '#/lib/api'
import { riskTypeLabel } from '#/lib/labels'
import { humanEvidenceLines } from '#/lib/trigger-metrics'
import { useSnapshot } from '#/context/SnapshotContext'
import { EvidenceTagList, TriggerMetricsGrid } from '#/components/buque/TriggerMetricsGrid'
import { GlassCard, RiskBadge } from '#/components/buque/RiskBadge'

type Props = {
  sku: string
  warehouse?: string
}

function formatDos(dos: string | null | undefined) {
  if (!dos) return '—'
  const n = Number(dos)
  return Number.isFinite(n) ? `${n.toFixed(1)} 天` : dos
}

function ExplanationLayer({
  title,
  text,
  emphasis = false,
}: {
  title: string
  text: string
  emphasis?: boolean
}) {
  return (
    <div className={emphasis ? 'buque-explain-primary' : 'buque-explain-layer'}>
      <div className="buque-explain-layer-title">{title}</div>
      <p className="buque-explain-layer-text">{text}</p>
    </div>
  )
}

export function SkuAlertDetailContent({ sku, warehouse }: Props) {
  const { selectedSnapshotId } = useSnapshot()
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.skuDetail(sku, selectedSnapshotId, warehouse),
    queryFn: () => api.skuDetail(sku, { warehouse, snapshotId: selectedSnapshotId }),
    enabled: selectedSnapshotId !== undefined,
  })

  const agentExplain = useMutation({
    mutationFn: () =>
      api.agentExplainSku(sku, {
        warehouse,
        snapshotId: selectedSnapshotId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.skuDetail(sku, selectedSnapshotId, warehouse),
      })
    },
  })

  if (isLoading) return <div className="demo-muted py-8 text-center text-sm">加载 SKU 分析卡…</div>
  if (error) return <div className="py-8 text-center text-sm text-[var(--status-danger)]">无法加载 SKU 详情。</div>
  if (!data) return null

  const explain = agentExplain.data
  const tags = explain?.explanation_tags ?? data.explanation_tags ?? []
  const evidenceLines = humanEvidenceLines(explain?.key_evidence ?? data.key_evidence)

  const primary = explain?.primary_explanation ?? data.primary_explanation
  const secondary = explain?.secondary_explanation ?? data.secondary_explanation
  const tertiary = explain?.tertiary_explanation ?? data.tertiary_explanation

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--hairline)] pb-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold text-[var(--sea-ink)]">{data.sku}</span>
            <RiskBadge level={data.risk_level} />
          </div>
          <p className="mt-1 text-sm text-[var(--sea-ink-soft)]">{data.product_name ?? '—'}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="buque-detail-chip">{data.warehouse ?? '全仓'}</span>
            <span className="buque-detail-chip">{riskTypeLabel(data.risk_type)}</span>
            <span className="buque-detail-chip">DOS {formatDos(data.dos)}</span>
            <span className="buque-detail-chip">监控日 {data.monitor_date}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="demo-button demo-button-sm"
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
            className="demo-button demo-button-secondary demo-button-sm no-underline"
          >
            <MessageSquarePlus size={16} />
            提交反馈
          </Link>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <GlassCard>
            <h2 className="demo-section-title mb-3">风险结论</h2>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-base font-semibold text-[var(--sea-ink)]">
                {riskTypeLabel(data.risk_type)}
              </span>
              <span className="text-sm text-[var(--sea-ink-soft)]">可售天数 {formatDos(data.dos)}</span>
              {tags.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((tag) => (
                    <span key={tag} className="buque-explain-tag">
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </GlassCard>

          <GlassCard>
            <h2 className="demo-section-title mb-3">触发证据</h2>
            <TriggerMetricsGrid
              triggerRule={data.trigger_rule}
              metrics={data.trigger_metrics}
            />
          </GlassCard>

          <GlassCard>
            <h2 className="demo-section-title mb-3">解释</h2>
            {agentExplain.error ? (
              <p className="mb-3 text-sm text-[var(--status-danger)]">
                深度分析失败：{(agentExplain.error as Error).message}
              </p>
            ) : null}
            {primary ? <ExplanationLayer title="主解释" text={primary} emphasis /> : null}
            {secondary ? <ExplanationLayer title="次解释" text={secondary} /> : null}
            {tertiary ? <ExplanationLayer title="第三解释" text={tertiary} /> : null}
            {!primary && !secondary && !tertiary ? (
              <p className="text-sm demo-muted">暂无解释内容</p>
            ) : null}
            {explain?.confidence_note ? (
              <p className="mt-3 text-xs demo-muted">{explain.confidence_note}</p>
            ) : null}
            {evidenceLines.length > 0 ? (
              <div className="mt-4 border-t border-[var(--hairline)] pt-3">
                <div className="mb-2 text-xs font-medium text-[var(--sea-ink-soft)]">证据摘要</div>
                <EvidenceTagList lines={evidenceLines} />
              </div>
            ) : null}
          </GlassCard>

          <GlassCard>
            <h2 className="demo-section-title mb-3">建议动作</h2>
            <p className="text-sm leading-relaxed text-[var(--sea-ink)]">
              {explain?.suggested_action ?? data.suggested_action ?? '—'}
            </p>
          </GlassCard>
        </div>

        <GlassCard className="h-fit">
          <h2 className="demo-section-title mb-3">处理信息</h2>
          <dl className="buque-detail-meta">
            <div className="buque-detail-meta-row">
              <dt>责任角色</dt>
              <dd>{explain?.responsible_role ?? data.responsible_role ?? '—'}</dd>
            </div>
            <div className="buque-detail-meta-row">
              <dt>建议时效</dt>
              <dd>{explain?.action_deadline ?? data.action_deadline ?? '—'}</dd>
            </div>
            <div className="buque-detail-meta-row">
              <dt>须人工确认</dt>
              <dd>{(explain?.require_human_confirm ?? data.require_human_confirm) ? '是' : '否'}</dd>
            </div>
            <div className="buque-detail-meta-row">
              <dt>业务日</dt>
              <dd>{data.monitor_date}</dd>
            </div>
          </dl>
        </GlassCard>
      </div>
    </div>
  )
}

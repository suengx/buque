import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { DosJudgmentPanel, inferJudgment } from '#/components/buque/DosJudgmentPanel'
import {
  DETAIL_EVIDENCE_KEYS,
  formatTriggerRule,
  triggerMetricRows,
} from '#/lib/trigger-metrics'
import { cn } from '#/lib/utils'

function MetricKvGrid({ rows }: { rows: ReturnType<typeof triggerMetricRows> }) {
  if (!rows.length) return null
  return (
    <div className="buque-metric-kv-grid">
      {rows.map((row) => (
        <div key={row.key} className="buque-metric-kv-item">
          <div className="buque-metric-kv-label">{row.label}</div>
          {row.hint ? <div className="buque-metric-kv-hint">{row.hint}</div> : null}
          <div className="buque-metric-kv-value">{row.value}</div>
        </div>
      ))}
    </div>
  )
}

type Props = {
  triggerRule?: string
  riskLevel: string
  metrics: Record<string, unknown>
  availableInventory?: number | null
  refDailySales?: number | null
  className?: string
}

export function TriggerMetricsGrid({
  triggerRule,
  riskLevel,
  metrics,
  availableInventory,
  refDailySales,
  className,
}: Props) {
  const [detailOpen, setDetailOpen] = useState(false)
  const judgment = inferJudgment(triggerRule, metrics, riskLevel)
  const detailRows = triggerMetricRows(metrics, DETAIL_EVIDENCE_KEYS)
  const fieldRows = 'field' in metrics ? triggerMetricRows(metrics, ['field']) : []

  if (!judgment && !detailRows.length && !fieldRows.length) {
    return <p className="text-sm demo-muted">无触发指标</p>
  }

  return (
    <div className={cn('space-y-4', className)}>
      {triggerRule ? (
        <div className="buque-evidence-rule">
          <span className="buque-evidence-rule-label">触发规则</span>
          <span className="buque-evidence-rule-value">{formatTriggerRule(triggerRule)}</span>
        </div>
      ) : null}

      {judgment ? (
        <section>
          <h3 className="buque-evidence-section-title">判定结论</h3>
          <p className="buque-evidence-section-desc">公式、阈值区间与最终档位</p>
          <DosJudgmentPanel
            judgment={judgment}
            availableInventory={availableInventory}
            refDailySales={refDailySales}
          />
        </section>
      ) : null}

      {detailRows.length > 0 || fieldRows.length > 0 ? (
        <section className="buque-detail-evidence">
          <button
            type="button"
            className="buque-detail-evidence-toggle"
            aria-expanded={detailOpen}
            onClick={() => setDetailOpen((v) => !v)}
          >
            <ChevronDown
              size={16}
              className={cn('transition-transform', !detailOpen && '-rotate-90')}
            />
            <span>细节证据</span>
            <span className="text-xs font-normal text-[var(--sea-ink-soft)]">
              参考日销来源、突增修正、订单 rollup 等
            </span>
          </button>
          {detailOpen ? (
            <div className="buque-detail-evidence-body">
              <MetricKvGrid rows={detailRows} />
              {fieldRows.length > 0 ? (
                <div className="mt-3">
                  <div className="mb-2 text-xs font-medium text-[var(--sea-ink-soft)]">数据质量</div>
                  <MetricKvGrid rows={fieldRows} />
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}

type EvidenceProps = {
  lines: string[]
}

export function EvidenceTagList({ lines }: EvidenceProps) {
  if (!lines.length) return null
  return (
    <div className="buque-evidence-tags">
      {lines.map((line) => (
        <span key={line} className="buque-evidence-tag">
          {line}
        </span>
      ))}
    </div>
  )
}

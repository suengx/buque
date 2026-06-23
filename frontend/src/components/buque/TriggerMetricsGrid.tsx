import { formatTriggerRule, triggerMetricRows } from '#/lib/trigger-metrics'
import { cn } from '#/lib/utils'

type Props = {
  triggerRule?: string
  metrics: Record<string, unknown>
  className?: string
}

export function TriggerMetricsGrid({ triggerRule, metrics, className }: Props) {
  const rows = triggerMetricRows(metrics)

  if (!triggerRule && rows.length === 0) {
    return <p className="text-sm demo-muted">无触发指标</p>
  }

  return (
    <div className={cn('space-y-3', className)}>
      {triggerRule ? (
        <div className="buque-evidence-rule">
          <span className="buque-evidence-rule-label">触发规则</span>
          <span className="buque-evidence-rule-value">{formatTriggerRule(triggerRule)}</span>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="buque-metric-kv-grid">
          {rows.map((row) => (
            <div key={row.key} className="buque-metric-kv-item">
              <div className="buque-metric-kv-label">{row.label}</div>
              {row.hint ? <div className="buque-metric-kv-hint">{row.hint}</div> : null}
              <div className="buque-metric-kv-value">{row.value}</div>
            </div>
          ))}
        </div>
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

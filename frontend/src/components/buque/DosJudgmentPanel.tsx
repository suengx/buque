import { RISK_LEVEL_LABEL } from '#/lib/labels'
import { RiskBadge } from '#/components/buque/RiskBadge'
import { cn } from '#/lib/utils'

export type JudgmentModifier = {
  rule: string
  label: string
  from_level: string
  to_level: string
}

export type DosJudgment = {
  kind: 'stockout_dos' | 'slow_moving_dos' | 'sales_ratio'
  formula: string
  compare?: string
  dos?: number
  available_inventory?: number
  ref_daily_sales?: number
  sales_3d_avg?: number
  sales_15d_avg?: number
  ratio?: number
  threshold?: number
  compare_label?: string
  threshold_red?: number
  threshold_orange?: number
  threshold_yellow?: number
  base_level: string
  base_level_label?: string
  final_level: string
  final_level_label?: string
  modifiers: JudgmentModifier[]
  bands: { level: string; label: string }[]
}

const BAND_ACCENT: Record<string, string> = {
  RED: 'buque-band-red',
  ORANGE: 'buque-band-orange',
  YELLOW: 'buque-band-yellow',
  GREEN: 'buque-band-green',
}

function num(v: unknown): number | null {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** 旧快照无 judgment 时，从 trigger_metrics 推导断货 DOS 判级 */
export function inferJudgment(
  triggerRule: string | undefined,
  metrics: Record<string, unknown>,
  riskLevel: string,
): DosJudgment | null {
  const embedded = metrics.judgment as DosJudgment | undefined
  if (embedded?.kind) return embedded

  const dos = num(metrics.dos)
  const red = num(metrics.threshold_red)
  if (dos === null || red === null) return null

  const orange = num(metrics.threshold_orange) ?? red * 1.5
  const yellow = num(metrics.threshold_yellow) ?? red * 2

  if (triggerRule === 'DOS_STOCKOUT') {
    let base = 'GREEN'
    if (dos <= red) base = 'RED'
    else if (dos <= orange) base = 'ORANGE'
    else if (dos <= yellow) base = 'YELLOW'
    return {
      kind: 'stockout_dos',
      formula: '可售库存 ÷ 有效参考日销',
      compare: 'low_is_worse',
      dos,
      threshold_red: red,
      threshold_orange: orange,
      threshold_yellow: yellow,
      base_level: base,
      base_level_label: RISK_LEVEL_LABEL[base],
      final_level: riskLevel,
      final_level_label: RISK_LEVEL_LABEL[riskLevel],
      modifiers: [],
      bands: [
        { level: 'RED', label: `DOS ≤ ${red} 天` },
        { level: 'ORANGE', label: `${red} < DOS ≤ ${Math.round(orange)} 天` },
        { level: 'YELLOW', label: `${Math.round(orange)} < DOS ≤ ${Math.round(yellow)} 天` },
        { level: 'GREEN', label: `DOS > ${Math.round(yellow)} 天` },
      ],
    }
  }

  if (triggerRule === 'DOS_SLOW_MOVING') {
    let base = 'GREEN'
    if (dos >= red) base = 'RED'
    else if (dos >= orange) base = 'ORANGE'
    else if (dos >= yellow) base = 'YELLOW'
    return {
      kind: 'slow_moving_dos',
      formula: '可售库存 ÷ 有效参考日销',
      compare: 'high_is_worse',
      dos,
      threshold_red: red,
      threshold_orange: orange,
      threshold_yellow: yellow,
      base_level: base,
      base_level_label: RISK_LEVEL_LABEL[base],
      final_level: riskLevel,
      final_level_label: RISK_LEVEL_LABEL[riskLevel],
      modifiers: [],
      bands: [
        { level: 'RED', label: `DOS ≥ ${red} 天` },
        { level: 'ORANGE', label: `${Math.round(orange)} ≤ DOS < ${red} 天` },
        { level: 'YELLOW', label: `${Math.round(yellow)} ≤ DOS < ${Math.round(orange)} 天` },
        { level: 'GREEN', label: `DOS < ${Math.round(yellow)} 天` },
      ],
    }
  }

  if (triggerRule === 'SALES_SURGE' || triggerRule === 'SALES_DROP') {
    const s3 = num(metrics.sales_3d_avg) ?? 0
    const s15 = num(metrics.sales_15d_avg) ?? 0
    const ratio = num(metrics.ratio) ?? (s15 > 0 ? s3 / s15 : 0)
    return {
      kind: 'sales_ratio',
      formula: '近 3 天日均 ÷ 近 15 天日均',
      compare: 'ratio',
      sales_3d_avg: s3,
      sales_15d_avg: s15,
      ratio,
      base_level: riskLevel,
      base_level_label: RISK_LEVEL_LABEL[riskLevel],
      final_level: riskLevel,
      final_level_label: RISK_LEVEL_LABEL[riskLevel],
      modifiers: [],
      bands: [],
    }
  }

  return null
}

function activeBandLevel(j: DosJudgment): string | null {
  if (j.kind === 'sales_ratio') return j.final_level
  const dos = j.dos
  if (dos === undefined) return null
  if (j.kind === 'stockout_dos') {
    const red = j.threshold_red ?? 0
    const orange = j.threshold_orange ?? red * 1.5
    const yellow = j.threshold_yellow ?? red * 2
    if (dos <= red) return 'RED'
    if (dos <= orange) return 'ORANGE'
    if (dos <= yellow) return 'YELLOW'
    return 'GREEN'
  }
  const red = j.threshold_red ?? 0
  const orange = j.threshold_orange ?? red * 0.85
  const yellow = j.threshold_yellow ?? red * 0.7
  if (dos >= red) return 'RED'
  if (dos >= orange) return 'ORANGE'
  if (dos >= yellow) return 'YELLOW'
  return 'GREEN'
}

type Props = {
  judgment: DosJudgment
  availableInventory?: number | null
  refDailySales?: number | null
}

export function DosJudgmentPanel({ judgment: j, availableInventory, refDailySales }: Props) {
  const dosBand = activeBandLevel(j)
  const avail = availableInventory ?? j.available_inventory
  const ref = refDailySales ?? j.ref_daily_sales

  return (
    <div className="buque-dos-judgment">
      {j.kind !== 'sales_ratio' && avail != null && ref != null && j.dos != null ? (
        <div className="buque-dos-formula">
          <span className="buque-dos-formula-label">DOS 计算</span>
          <span className="buque-dos-formula-expr">
            可售库存（{Math.round(avail)} 件）÷ 有效参考日销（{ref.toFixed(2)} 件/天）={' '}
            <strong>{j.dos.toFixed(1)} 天</strong>
          </span>
          <span className="buque-dos-formula-hint">分母不含在途</span>
        </div>
      ) : j.kind === 'sales_ratio' ? (
        <div className="buque-dos-formula">
          <span className="buque-dos-formula-label">销量比值</span>
          <span className="buque-dos-formula-expr">
            近 3 天日均（{(j.sales_3d_avg ?? 0).toFixed(2)} 件/天）÷ 近 15 天日均（
            {(j.sales_15d_avg ?? 0).toFixed(2)} 件/天）={' '}
            <strong>{((j.ratio ?? 0) * 100).toFixed(0)}%</strong>
          </span>
          {j.compare_label ? (
            <span className="buque-dos-formula-hint">判定：{j.compare_label}</span>
          ) : null}
        </div>
      ) : null}

      {j.bands.length > 0 ? (
        <div className="buque-dos-bands">
          <span className="buque-dos-bands-title">DOS 档位区间</span>
          <ul className="buque-dos-band-list">
            {j.bands.map((band) => (
              <li
                key={band.level}
                className={cn(
                  'buque-dos-band',
                  BAND_ACCENT[band.level],
                  dosBand === band.level && 'buque-dos-band-active',
                )}
              >
                <RiskBadge level={band.level} />
                <span>{band.label}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="buque-dos-verdict">
        <div className="buque-dos-verdict-row">
          <span className="buque-dos-verdict-label">DOS 基准档位</span>
          <RiskBadge level={j.base_level} />
          <span className="text-sm text-[var(--sea-ink-soft)]">
            {j.base_level_label ?? RISK_LEVEL_LABEL[j.base_level]}
          </span>
        </div>

        {j.modifiers.length > 0 ? (
          <ul className="buque-dos-modifiers">
            {j.modifiers.map((m) => (
              <li key={`${m.rule}-${m.from_level}-${m.to_level}`}>
                <span className="buque-dos-modifier-label">{m.label}</span>
                <span className="buque-dos-modifier-arrow">
                  {RISK_LEVEL_LABEL[m.from_level] ?? m.from_level} →{' '}
                  {RISK_LEVEL_LABEL[m.to_level] ?? m.to_level}
                </span>
              </li>
            ))}
          </ul>
        ) : j.base_level !== j.final_level ? (
          <p className="buque-dos-modifier-missing text-xs text-[var(--sea-ink-soft)]">
            最终档位与 DOS 基准不一致，可能经突增升档、在途缓释或重点链接等规则修正；重新「同步并分析」可查看完整修正链。
          </p>
        ) : null}

        <div className="buque-dos-verdict-row buque-dos-verdict-final">
          <span className="buque-dos-verdict-label">最终档位</span>
          <RiskBadge level={j.final_level} />
          <span className="font-medium text-[var(--sea-ink)]">
            {j.final_level_label ?? RISK_LEVEL_LABEL[j.final_level]}
          </span>
        </div>
      </div>
    </div>
  )
}

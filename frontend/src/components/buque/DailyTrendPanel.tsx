import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { useState } from 'react'
import type { ReportAnalytics, TrendComparison } from '#/lib/api'
import { RiskTrendChart } from '#/components/buque/ReportCharts'
import { cn } from '#/lib/utils'

type CompareMode = 'prev_day' | 'prev_snapshot'

const COMPARE_OPTIONS: {
  mode: CompareMode
  label: string
  title: string
}[] = [
  {
    mode: 'prev_day',
    label: '较昨日',
    title: '与上一业务日的最新成功快照对比',
  },
  {
    mode: 'prev_snapshot',
    label: '较上次',
    title: '与按完成时间排序的上一条成功快照对比（同业务日重跑也计入）',
  },
]

function DeltaBadge({
  label,
  value,
  tone,
  hint,
}: {
  label: string
  value: number
  tone: 'red' | 'orange'
  hint: string
}) {
  const DeltaIcon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus
  return (
    <div className={`buque-trend-delta buque-trend-delta-${tone}`}>
      <span className="buque-trend-delta-label">{label}</span>
      <span className="buque-trend-delta-value">
        <DeltaIcon size={14} />
        {value}
      </span>
      <span className="buque-trend-delta-hint">{hint}</span>
    </div>
  )
}

export function DailyTrendPanel({
  trend,
  comparisonVsPrevDay,
  comparisonVsPrevSnapshot,
}: {
  trend: ReportAnalytics['trend_7d']
  comparisonVsPrevDay: TrendComparison
  comparisonVsPrevSnapshot: TrendComparison
}) {
  const [mode, setMode] = useState<CompareMode>('prev_day')
  const active = mode === 'prev_day' ? comparisonVsPrevDay : comparisonVsPrevSnapshot
  const activeOption = COMPARE_OPTIONS.find((o) => o.mode === mode) ?? COMPARE_OPTIONS[0]

  return (
    <section className="buque-trend-panel">
      <div className="buque-trend-panel-head">
        <div className="min-w-0">
          <h2 className="demo-section-title text-base">预警趋势</h2>
          <p className="mt-0.5 text-xs text-[var(--sea-ink-soft)]">
            近 7 日 · 仓库作用域
            {active.baseline_label ? (
              <>
                <span className="mx-1">·</span>
                <span title={activeOption.title}>基准 {active.baseline_label}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="buque-trend-panel-actions">
          <div className="buque-trend-compare" role="tablist" aria-label="新增对比基准">
            {COMPARE_OPTIONS.map((option) => {
              const disabled =
                option.mode === 'prev_snapshot' && !comparisonVsPrevSnapshot.available
              return (
                <button
                  key={option.mode}
                  type="button"
                  role="tab"
                  aria-selected={mode === option.mode}
                  className={cn(
                    'buque-trend-compare-btn',
                    mode === option.mode && 'buque-trend-compare-btn-active',
                  )}
                  title={disabled ? '暂无上序快照' : option.title}
                  disabled={disabled}
                  onClick={() => setMode(option.mode)}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
          <div className="buque-trend-deltas">
            <DeltaBadge
              label="新增红灯"
              value={active.new_red_count}
              tone="red"
              hint={activeOption.label}
            />
            <DeltaBadge
              label="新增橙灯"
              value={active.new_orange_count}
              tone="orange"
              hint={activeOption.label}
            />
          </div>
        </div>
      </div>
      <RiskTrendChart trend={trend} embedded />
    </section>
  )
}

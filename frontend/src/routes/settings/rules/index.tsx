import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Boxes, CircleCheck, CircleOff, Sliders } from 'lucide-react'
import { api, queryKeys } from '#/lib/api'
import { MetricCard } from '#/components/buque/MetricCard'
import { PageHeader } from '#/components/buque/PageHeader'
import { RulesTable, type RuleTableRow } from '#/components/buque/RulesTable'
import { SectionBlock } from '#/components/buque/SectionBlock'

type RulesSearch = {
  focus?: string
}

const RISK_CATEGORIES = new Set(['stockout', 'slow_moving', 'sales', 'inbound', 'upgrade'])

export const Route = createFileRoute('/settings/rules/')({
  validateSearch: (search: Record<string, unknown>): RulesSearch => ({
    focus: (search.focus as string) || undefined,
  }),
  component: RulesSettingsPage,
})

function pct(count: number, total: number) {
  if (total <= 0) return '0%'
  return `${((count / total) * 100).toFixed(1)}%`
}

function RulesSettingsPage() {
  const { focus } = Route.useSearch()
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.rules,
    queryFn: () => api.listRules(),
  })

  const rules = useMemo<RuleTableRow[]>(() => {
    if (!data) return []
    return data.groups.flatMap((g) =>
      g.rules.map((r) => ({
        ...r,
        category_label: g.category_label,
      })),
    )
  }, [data])

  const stats = useMemo(() => {
    const total = rules.length
    const enabled = rules.filter((r) => r.is_enabled).length
    const disabled = total - enabled
    const riskGrading = rules.filter((r) => RISK_CATEGORIES.has(r.category)).length
    const categories = data?.groups.length ?? 0
    return { total, enabled, disabled, riskGrading, categories }
  }, [rules, data])

  if (isLoading) return <div className="demo-muted">加载规则配置…</div>
  if (error) return <div className="text-[var(--status-danger)]">无法加载规则配置。</div>
  if (!data) return null

  return (
    <div className="buque-page-stack">
      <PageHeader
        title="规则配置"
        subtitle="风险判级与系统参数"
        tooltip="变更在下次「同步并分析」后生效；红灯/橙灯阈值变更须填写变更原因。"
      />

      <div className="buque-rule-notice">
        配置变更不会回溯已有快照，仅影响下一次流水线分析结果。
      </div>

      <SectionBlock label="概览" description="当前生效规则统计">
        <div className="buque-metric-grid buque-metric-grid-4">
          <MetricCard
            title="规则总数"
            value={stats.total}
            description={`${stats.categories} 个分类`}
            icon={Sliders}
            accent="neutral"
          />
          <MetricCard
            title="已启用"
            value={stats.enabled}
            percent={pct(stats.enabled, stats.total)}
            description="参与判级与流水线"
            icon={CircleCheck}
            accent="green"
          />
          <MetricCard
            title="已停用"
            value={stats.disabled}
            percent={pct(stats.disabled, stats.total)}
            description="当前未生效"
            icon={CircleOff}
            accent="neutral"
          />
          <MetricCard
            title="判级相关"
            value={stats.riskGrading}
            percent={pct(stats.riskGrading, stats.total)}
            description="断货/滞销/销量/在途/升级"
            icon={Boxes}
            accent="orange"
          />
        </div>
      </SectionBlock>

      <RulesTable rules={rules} focus={focus} />
    </div>
  )
}

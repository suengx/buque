import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, queryKeys } from '#/lib/api'
import { GlassCard, StatCard } from '#/components/buque/RiskBadge'
import { SyncErpDialog } from '#/components/buque/SyncErpDialog'

export const Route = createFileRoute('/')({
  component: DailyReportPage,
})

function DailyReportPage() {
  const [syncOpen, setSyncOpen] = useState(false)
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.dailyReport(),
    queryFn: () => api.dailyReport(),
  })

  if (isLoading) return <div className="p-8">加载日报...</div>
  if (error) return <div className="p-8 text-red-600">无法加载日报，请确认后端已启动。</div>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0B3D3A]">日报总览</h1>
          <p className="text-sm text-[#45515A]">监控日期：{data?.monitor_date}</p>
        </div>
        <button type="button" className="demo-button" onClick={() => setSyncOpen(true)}>
          同步 ERP
        </button>
      </div>
      <SyncErpDialog
        open={syncOpen}
        onClose={() => setSyncOpen(false)}
        monitorDate={data?.monitor_date}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="监控 SKU" value={data?.monitored_sku_count ?? 0} />
        <StatCard title="新增红灯" value={data?.new_red_count ?? 0} hint="较昨日" />
        <StatCard title="新增橙灯" value={data?.new_orange_count ?? 0} hint="较昨日" />
        <StatCard title="今日优先处理" value={data?.priority_today_count ?? 0} />
        <StatCard title="断货高风险" value={data?.stockout_high_risk_count ?? 0} />
        <StatCard title="滞销高风险" value={data?.slow_moving_high_risk_count ?? 0} />
        <StatCard title="销量异常" value={data?.sales_anomaly_count ?? 0} />
        <StatCard title="数据异常" value={data?.data_anomaly_count ?? 0} />
      </div>
      <GlassCard>
        <h2 className="mb-2 font-semibold text-[#0B3D3A]">GLOBAL 汇总说明</h2>
        <p className="text-sm text-[#45515A]">
          风险清单默认展示 WAREHOUSE 作用域；本页 KPI 含全仓监控规模与红橙灯变化。
        </p>
      </GlassCard>
    </div>
  )
}

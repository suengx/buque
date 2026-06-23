import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, queryKeys } from '#/lib/api'
import { RiskBadge } from '#/components/buque/RiskBadge'

export const Route = createFileRoute('/alerts/')({
  component: AlertsPage,
})

function AlertsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.alerts({ page: 1, page_size: 50 }),
    queryFn: () => api.alerts({ page: 1, page_size: 50 }),
  })

  if (isLoading) return <div className="p-8 demo-muted">加载风险清单...</div>
  if (error) return <div className="p-8 text-[var(--status-danger)]">无法加载风险清单。</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="demo-title text-2xl">风险预警中心</h1>
        <p className="text-sm demo-muted">WAREHOUSE 作用域 · 共 {data?.total ?? 0} 条</p>
      </div>
      <div className="demo-table-shell">
        <table className="demo-table w-full min-w-[960px]">
          <thead>
            <tr>
              <th>SKU</th>
              <th>产品</th>
              <th>仓库</th>
              <th>风险类型</th>
              <th>等级</th>
              <th>DOS</th>
              <th>主解释</th>
              <th>状态</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((row) => (
              <tr key={row.id}>
                <td className="font-medium">{row.sku}</td>
                <td>{row.product_name ?? '-'}</td>
                <td>{row.warehouse ?? '-'}</td>
                <td>{row.risk_type}</td>
                <td>
                  <RiskBadge level={row.risk_level} />
                </td>
                <td>{row.dos ?? '-'}</td>
                <td className="max-w-xs truncate">{row.primary_explanation ?? '-'}</td>
                <td>{row.handling_status}</td>
                <td>
                  <Link
                    to="/alerts/$skuId"
                    params={{ skuId: row.sku }}
                    search={{ warehouse: row.warehouse ?? undefined }}
                    className="text-[var(--aqua)] hover:underline"
                  >
                    详情
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

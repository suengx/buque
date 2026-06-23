import { Search, RotateCcw } from 'lucide-react'
import { cn } from '#/lib/utils'

export type FilterValues = {
  level?: string
  risk_type?: string
  warehouse?: string
  sku?: string
}

type Props = {
  values: FilterValues
  warehouses: string[]
  onChange: (patch: Partial<FilterValues>) => void
  onReset: () => void
  onSubmit: () => void
  embedded?: boolean
}

function FilterInline({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <label className={cn('buque-filter-inline', className)}>
      <span className="buque-filter-inline-label">{label}</span>
      {children}
    </label>
  )
}

export function FilterBar({ values, warehouses, onChange, onReset, onSubmit, embedded }: Props) {
  return (
    <div className={cn('buque-filter-bar', embedded && 'buque-filter-bar-embedded')}>
      <FilterInline label="等级">
        <select
          className="buque-filter-control"
          value={values.level ?? ''}
          onChange={(e) => onChange({ level: e.target.value || undefined })}
        >
          <option value="">全部</option>
          <option value="RED">高风险</option>
          <option value="ORANGE">中风险</option>
          <option value="YELLOW">低风险</option>
          <option value="GREEN">绿灯</option>
        </select>
      </FilterInline>
      <FilterInline label="类型">
        <select
          className="buque-filter-control"
          value={values.risk_type ?? ''}
          onChange={(e) => onChange({ risk_type: e.target.value || undefined })}
        >
          <option value="">全部</option>
          <option value="STOCKOUT">断货风险</option>
          <option value="SLOW_MOVING">滞销风险</option>
          <option value="SALES_ANOMALY">销量异常</option>
        </select>
      </FilterInline>
      <FilterInline label="仓库" className="min-w-[148px]">
        <select
          className="buque-filter-control"
          value={values.warehouse ?? ''}
          onChange={(e) => onChange({ warehouse: e.target.value || undefined })}
        >
          <option value="">全部</option>
          {warehouses.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </FilterInline>
      <FilterInline label="SKU" className="min-w-[132px] flex-1">
        <input
          className="buque-filter-control"
          placeholder="搜索 SKU"
          value={values.sku ?? ''}
          onChange={(e) => onChange({ sku: e.target.value || undefined })}
        />
      </FilterInline>
      <div className="buque-filter-actions">
        <button type="button" className="demo-button demo-button-secondary demo-button-sm" onClick={onReset}>
          <RotateCcw size={13} />
          重置
        </button>
        <button type="button" className="demo-button demo-button-sm" onClick={onSubmit}>
          <Search size={13} />
          筛选
        </button>
      </div>
    </div>
  )
}

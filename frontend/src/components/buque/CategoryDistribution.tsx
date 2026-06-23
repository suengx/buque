export type DistributionItem = {
  key: string
  label: string
  value: number
  color: string
}

type Props = {
  title: string
  subtitle?: string
  items: DistributionItem[]
  showPercent?: boolean
  onBarClick?: (key: string) => void
  emptyText?: string
  bordered?: boolean
}

function pct(value: number, total: number) {
  if (total <= 0) return '0%'
  return `${((value / total) * 100).toFixed(1)}%`
}

export function CategoryDistribution({
  title,
  subtitle,
  items,
  showPercent = true,
  onBarClick,
  emptyText = '暂无数据',
  bordered = false,
}: Props) {
  const total = items.reduce((sum, item) => sum + item.value, 0)
  const max = Math.max(...items.map((i) => i.value), 1)

  const content = (
    <>
      <div className="mb-2">
        <h3 className="buque-distribution-chart-title">{title}</h3>
        {subtitle ? <p className="buque-distribution-chart-subtitle">{subtitle}</p> : null}
      </div>
      {items.length === 0 ? (
        <div className="py-6 text-center text-sm text-[var(--sea-ink-soft)]">{emptyText}</div>
      ) : (
        <div className="space-y-0.5">
          {items.map((item) => {
            const width = `${Math.max((item.value / max) * 100, item.value > 0 ? 4 : 0)}%`
            const row = (
              <>
                <span className="buque-distribution-bar-label">{item.label}</span>
                <div className="buque-distribution-bar-track">
                  <div
                    className="buque-distribution-bar-fill"
                    style={{ width, backgroundColor: item.color }}
                  />
                </div>
                <span className="buque-distribution-bar-meta">
                  {item.value}
                  {showPercent ? (
                    <span className="buque-distribution-bar-pct"> · {pct(item.value, total)}</span>
                  ) : null}
                </span>
              </>
            )
            if (onBarClick) {
              return (
                <button
                  key={item.key}
                  type="button"
                  className="buque-distribution-bar-row buque-distribution-bar-row-clickable w-full border-0 bg-transparent text-left"
                  onClick={() => onBarClick(item.key)}
                >
                  {row}
                </button>
              )
            }
            return (
              <div key={item.key} className="buque-distribution-bar-row">
                {row}
              </div>
            )
          })}
        </div>
      )}
    </>
  )

  if (bordered) {
    return <div className="buque-panel-flat">{content}</div>
  }

  return <div>{content}</div>
}

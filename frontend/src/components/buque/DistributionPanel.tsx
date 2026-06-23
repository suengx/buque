import { CategoryDistribution } from '#/components/buque/CategoryDistribution'
import {
  levelDistributionItems,
  typeDistributionItems,
} from '#/lib/risk-tokens'

type Props = {
  levelCounts: Record<string, number>
  typeCounts: Record<string, number>
  onLevelClick?: (level: string) => void
  onTypeClick?: (riskType: string) => void
}

export function DistributionPanel({
  levelCounts,
  typeCounts,
  onLevelClick,
  onTypeClick,
}: Props) {
  const levelItems = levelDistributionItems(levelCounts, false)
  const typeItems = typeDistributionItems(typeCounts)

  return (
    <div className="buque-panel-flat">
      <div className="buque-distribution-split">
        <CategoryDistribution
          title="风险等级分布"
          subtitle="红 / 橙 / 黄"
          items={levelItems}
          onBarClick={onLevelClick}
        />
        <CategoryDistribution
          title="风险类型分布"
          subtitle="全等级计数"
          items={typeItems}
          onBarClick={onTypeClick}
        />
      </div>
    </div>
  )
}

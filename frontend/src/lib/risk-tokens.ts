import { RISK_LEVEL_LABEL, RISK_TYPE_LABEL } from '#/lib/labels'

export type RiskLevel = 'RED' | 'ORANGE' | 'YELLOW' | 'GREEN'
export type RiskType = 'STOCKOUT' | 'SLOW_MOVING' | 'SALES_ANOMALY' | 'DATA_ANOMALY'

export const RISK_LEVEL_ORDER: RiskLevel[] = ['RED', 'ORANGE', 'YELLOW', 'GREEN']

export const RISK_LEVEL_CSS: Record<RiskLevel, { chart: string; surface: string; ink: string; border: string }> = {
  RED: {
    chart: 'var(--risk-red-chart)',
    surface: 'var(--risk-red-bg)',
    ink: 'var(--risk-red-text)',
    border: 'var(--risk-red-border)',
  },
  ORANGE: {
    chart: 'var(--risk-orange-chart)',
    surface: 'var(--risk-orange-bg)',
    ink: 'var(--risk-orange-text)',
    border: 'var(--risk-orange-border)',
  },
  YELLOW: {
    chart: 'var(--risk-yellow-chart)',
    surface: 'var(--risk-yellow-bg)',
    ink: 'var(--risk-yellow-text)',
    border: 'var(--risk-yellow-border)',
  },
  GREEN: {
    chart: 'var(--risk-green-chart)',
    surface: 'var(--risk-green-bg)',
    ink: 'var(--risk-green-text)',
    border: 'var(--risk-green-border)',
  },
}

export const RISK_TYPE_CSS: Record<string, string> = {
  STOCKOUT: 'var(--risk-red-chart)',
  SLOW_MOVING: 'var(--risk-orange-chart)',
  SALES_ANOMALY: 'var(--risk-type-sales-chart)',
  DATA_ANOMALY: 'var(--slate)',
}

export const HIDDEN_RISK_TYPES = new Set(['DATA_ANOMALY'])

export function levelDistributionItems(counts: Record<string, number>, includeGreen = true) {
  const levels = includeGreen ? RISK_LEVEL_ORDER : RISK_LEVEL_ORDER.filter((l) => l !== 'GREEN')
  return levels
    .map((key) => ({
      key,
      label: RISK_LEVEL_LABEL[key] ?? key,
      value: counts[key] ?? 0,
      color: RISK_LEVEL_CSS[key].chart,
    }))
    .filter((item) => item.value > 0)
}

export function typeDistributionItems(counts: Record<string, number>) {
  return Object.entries(counts)
    .filter(([k, v]) => v > 0 && !HIDDEN_RISK_TYPES.has(k))
    .map(([key, value]) => ({
      key,
      label: RISK_TYPE_LABEL[key] ?? key,
      value,
      color: RISK_TYPE_CSS[key] ?? 'var(--aqua)',
    }))
    .sort((a, b) => b.value - a.value)
}

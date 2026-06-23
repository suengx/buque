export const RISK_LEVEL_LABEL: Record<string, string> = {
  RED: '红灯',
  ORANGE: '橙灯',
  YELLOW: '黄灯',
  GREEN: '绿灯',
}

export const RISK_TYPE_LABEL: Record<string, string> = {
  STOCKOUT: '断货风险',
  SLOW_MOVING: '滞销风险',
  SALES_ANOMALY: '销量异常',
  DATA_ANOMALY: '数据异常',
  FORECAST_BIAS: '预测偏差',
}

export const HANDLING_STATUS_LABEL: Record<string, string> = {
  UNPROCESSED: '待处理',
  PROCESSING: '处理中',
  HANDLED: '已处理',
}

export const HANDLING_STATUS_TONE: Record<string, 'danger' | 'warning' | 'success'> = {
  UNPROCESSED: 'danger',
  PROCESSING: 'warning',
  HANDLED: 'success',
}

export function riskTypeLabel(value: string) {
  return RISK_TYPE_LABEL[value] ?? value
}

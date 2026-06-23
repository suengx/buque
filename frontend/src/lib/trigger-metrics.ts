export type TriggerMetricField = {
  key: string
  label: string
  hint: string
  format: (value: unknown) => string
}

const num = (value: unknown): number | null => {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export const TRIGGER_RULE_LABEL: Record<string, string> = {
  DOS_STOCKOUT: '断货 DOS 判级',
  DOS_SLOW_MOVING: '滞销 DOS 判级',
  SALES_SURGE: '销量突增判级',
  SALES_DROP: '销量突降判级',
  SALES_ANOMALY: '销量异常判级',
  MISSING_DATA_BLOCK: '关键字段缺失拦截',
}

export const TRIGGER_METRIC_FIELDS: Record<string, TriggerMetricField> = {
  dos: {
    key: 'dos',
    label: '可售天数 DOS',
    hint: '可售库存 ÷ 参考日销',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${n.toFixed(1)} 天`
    },
  },
  threshold_red: {
    key: 'threshold_red',
    label: '红灯阈值',
    hint: '规则配置的红灯 DOS 线',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${Math.round(n)} 天`
    },
  },
  sales_3d_avg: {
    key: 'sales_3d_avg',
    label: '近 3 天日均销量',
    hint: '近 3 天订购量均值',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${n.toFixed(2)} 件/天`
    },
  },
  sales_15d_avg: {
    key: 'sales_15d_avg',
    label: '近 15 天日均销量',
    hint: '近 15 天订购量均值',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${n.toFixed(2)} 件/天`
    },
  },
  ratio: {
    key: 'ratio',
    label: '销量比值',
    hint: '近 3 天 ÷ 近 15 天',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${(n * 100).toFixed(0)}%`
    },
  },
  field: {
    key: 'field',
    label: '异常字段',
    hint: '数据质量拦截字段',
    format: (v) => (v == null || v === '' ? '—' : String(v)),
  },
}

const METRIC_ORDER = ['dos', 'threshold_red', 'sales_3d_avg', 'sales_15d_avg', 'ratio', 'field']

export function triggerMetricRows(metrics: Record<string, unknown>) {
  const keys = [
    ...METRIC_ORDER.filter((k) => k in metrics),
    ...Object.keys(metrics).filter((k) => !METRIC_ORDER.includes(k)),
  ]
  return keys.map((key) => {
    const field = TRIGGER_METRIC_FIELDS[key] ?? {
      key,
      label: key,
      hint: '',
      format: (v: unknown) => (v == null ? '—' : String(v)),
    }
    return {
      key,
      label: field.label,
      hint: field.hint,
      value: field.format(metrics[key]),
    }
  })
}

/** 过滤历史数据里 str(dict) 形式的原始 JSON 证据行 */
export function humanEvidenceLines(lines: string[] | undefined) {
  if (!lines?.length) return []
  return lines.filter((line) => {
    const t = line.trim()
    if (!t) return false
    if (t.startsWith('{') && t.endsWith('}')) return false
    return true
  })
}

export function formatTriggerRule(rule: string | undefined) {
  if (!rule) return '—'
  return TRIGGER_RULE_LABEL[rule] ?? rule
}

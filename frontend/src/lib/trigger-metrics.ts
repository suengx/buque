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

export const REF_SALES_SOURCE_LABEL: Record<string, string> = {
  ERP_7D_AVG: 'ERP 7 天日均',
}

export const DETAIL_EVIDENCE_KEYS = [
  'erp_ref_daily_sales',
  'ref_daily_sales',
  'ref_sales_source',
  'sales_spike_trim_applied',
  'sales_3d_avg',
  'sales_15d_avg',
  'ratio',
] as const

export const DOS_BASIS_KEYS = [
  'available_inventory',
  'dos',
  'threshold_red',
  'threshold_orange',
  'threshold_yellow',
] as const

export const SALES_AUX_KEYS = ['sales_3d_avg', 'sales_15d_avg', 'ratio'] as const

export const TRIGGER_METRIC_FIELDS: Record<string, TriggerMetricField> = {
  available_inventory: {
    key: 'available_inventory',
    label: '可售库存',
    hint: 'DOS 分子，不含在途',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${Math.round(n)} 件`
    },
  },
  erp_ref_daily_sales: {
    key: 'erp_ref_daily_sales',
    label: 'ERP 7 天日均',
    hint: '产品库存页原始参考日销',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${n.toFixed(2)} 件/天`
    },
  },
  ref_daily_sales: {
    key: 'ref_daily_sales',
    label: '有效参考日销',
    hint: '经规则配置修正后的 DOS 分母',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${n.toFixed(2)} 件/天`
    },
  },
  ref_sales_source: {
    key: 'ref_sales_source',
    label: '参考日销来源',
    hint: 'BASE_SALES_PRIORITY 配置',
    format: (v) => REF_SALES_SOURCE_LABEL[String(v)] ?? String(v ?? '—'),
  },
  sales_spike_trim_applied: {
    key: 'sales_spike_trim_applied',
    label: '突增修正',
    hint: 'SALES_SPIKE_TRIM 是否压低分母',
    format: (v) => (v === true || v === 'true' || v === 1 ? '已应用' : '未应用'),
  },
  dos: {
    key: 'dos',
    label: '可售天数 DOS',
    hint: '可售库存 ÷ 有效参考日销',
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
  threshold_orange: {
    key: 'threshold_orange',
    label: '橙灯上限',
    hint: '红灯阈值 × 橙灯倍率',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${Math.round(n)} 天`
    },
  },
  threshold_yellow: {
    key: 'threshold_yellow',
    label: '黄灯上限',
    hint: '红灯阈值 × 黄灯倍率',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${Math.round(n)} 天`
    },
  },
  sales_3d_avg: {
    key: 'sales_3d_avg',
    label: '近 3 天日均销量',
    hint: '订单 rollup，辅助突增/异常判级',
    format: (v) => {
      const n = num(v)
      return n === null ? '—' : `${n.toFixed(2)} 件/天`
    },
  },
  sales_15d_avg: {
    key: 'sales_15d_avg',
    label: '近 15 天日均销量',
    hint: '订单 rollup，辅助突增/异常判级',
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

export function triggerMetricRows(metrics: Record<string, unknown>, keys: readonly string[]) {
  return keys
    .filter((key) => key in metrics)
    .map((key) => {
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

export function isSalesAnomalyRule(rule: string | undefined) {
  return rule === 'SALES_SURGE' || rule === 'SALES_DROP' || rule === 'SALES_ANOMALY'
}

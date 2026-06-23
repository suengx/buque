import type { RuleConfigItem } from '#/lib/api'

export function formatRuleParamValue(rule: RuleConfigItem): string {
  const val = rule.param_value.trim()
  if (rule.editor === 'bool') {
    return val.toLowerCase() === 'true' ? '开启' : '关闭'
  }
  if (rule.editor === 'tags') {
    return val.split(',').map((s) => s.trim()).filter(Boolean).join('、') || '—'
  }
  return val || '—'
}

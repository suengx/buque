import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History, Pencil } from 'lucide-react'
import { Fragment, useEffect, useRef, useState } from 'react'
import { api, queryKeys, type RuleConfigItem } from '#/lib/api'
import { formatRuleParamValue } from '#/lib/rule-display'
import { BuqueModal } from '#/components/buque/BuqueModal'
import { RuleEnableStatus } from '#/components/buque/RuleEnableStatus'
import { cn } from '#/lib/utils'

export type RuleTableRow = RuleConfigItem & {
  category_label: string
}

type RuleDraft = {
  param_value: string
  is_enabled: boolean
}

function RuleValueEditor({
  rule,
  value,
  onChange,
}: {
  rule: RuleConfigItem
  value: string
  onChange: (v: string) => void
}) {
  if (rule.editor === 'bool') {
    const checked = value.toLowerCase() === 'true'
    return (
      <label className="buque-rule-switch">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked ? 'true' : 'false')}
        />
        <span>{checked ? '开启' : '关闭'}</span>
      </label>
    )
  }
  if (rule.editor === 'int' || rule.editor === 'float') {
    return (
      <input
        type="number"
        step={rule.editor === 'float' ? '0.01' : '1'}
        className="demo-input buque-rule-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }
  return (
    <input
      className="demo-input buque-rule-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={rule.editor === 'tags' ? '逗号分隔' : undefined}
    />
  )
}

function RuleHistoryModal({
  rule,
  open,
  onClose,
}: {
  rule: RuleTableRow
  open: boolean
  onClose: () => void
}) {
  const { data: history, isLoading, error } = useQuery({
    queryKey: queryKeys.ruleHistory(rule.rule_code),
    queryFn: () => api.getRuleHistory(rule.rule_code),
    enabled: open,
  })

  return (
    <BuqueModal open={open} title={`${rule.rule_name} · 变更历史`} onClose={onClose}>
      {isLoading ? (
        <p className="text-sm text-[var(--sea-ink-soft)]">加载中…</p>
      ) : error ? (
        <p className="text-sm text-[var(--status-danger)]">无法加载变更历史。</p>
      ) : !history?.length ? (
        <p className="text-sm text-[var(--sea-ink-soft)]">暂无历史版本。</p>
      ) : (
        <div className="buque-alerts-table-wrap buque-rule-history-wrap">
          <table className="buque-alerts-table">
            <thead>
              <tr>
                <th>版本</th>
                <th>参数值</th>
                <th>状态</th>
                <th>生效日</th>
                <th>变更原因</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.version}>
                  <td>v{h.version}</td>
                  <td>{formatRuleParamValue(h)}</td>
                  <td>
                    <RuleEnableStatus enabled={h.is_enabled} />
                  </td>
                  <td>{h.effective_date}</td>
                  <td>{h.change_reason ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </BuqueModal>
  )
}

function draftFromRule(rule: RuleTableRow): RuleDraft {
  return {
    param_value: rule.param_value,
    is_enabled: rule.is_enabled,
  }
}

function isDraftDirty(rule: RuleTableRow, draft: RuleDraft) {
  return draft.param_value !== rule.param_value || draft.is_enabled !== rule.is_enabled
}

function RuleRow({ rule, focused }: { rule: RuleTableRow; focused: boolean }) {
  const qc = useQueryClient()
  const rowRef = useRef<HTMLTableRowElement>(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<RuleDraft>(() => draftFromRule(rule))
  const [reason, setReason] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)

  useEffect(() => {
    if (!editing) setDraft(draftFromRule(rule))
  }, [rule.param_value, rule.is_enabled, rule.version, editing])

  useEffect(() => {
    if (!focused || !rowRef.current) return
    rowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focused])

  const mutation = useMutation({
    mutationFn: () =>
      api.updateRule(rule.rule_code, {
        param_value: draft.param_value !== rule.param_value ? draft.param_value : undefined,
        is_enabled: draft.is_enabled !== rule.is_enabled ? draft.is_enabled : undefined,
        change_reason: reason,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.rules })
      qc.invalidateQueries({ queryKey: queryKeys.metricLabels })
      qc.invalidateQueries({ queryKey: queryKeys.ruleHistory(rule.rule_code) })
      setReason('')
      setEditing(false)
    },
  })

  const dirty = editing && isDraftDirty(rule, draft)

  const cancelEdit = () => {
    setDraft(draftFromRule(rule))
    setReason('')
    setEditing(false)
    mutation.reset()
  }

  return (
    <Fragment>
      <tr ref={rowRef} id={`rule-${rule.rule_code}`} className={cn(focused && 'buque-rule-row-focus')}>
        <td className="whitespace-nowrap text-sm text-[var(--sea-ink-soft)]">{rule.category_label}</td>
        <td className="min-w-[11rem] font-medium text-[var(--sea-ink)]">{rule.rule_name}</td>
        <td className="max-w-[300px] text-sm leading-snug text-[var(--sea-ink-soft)]">
          <span className="line-clamp-2">{rule.description}</span>
        </td>
        <td className="min-w-[7rem] text-sm text-[var(--sea-ink)]">
          {editing ? (
            <RuleValueEditor
              rule={rule}
              value={draft.param_value}
              onChange={(v) => setDraft((d) => ({ ...d, param_value: v }))}
            />
          ) : (
            formatRuleParamValue(rule)
          )}
        </td>
        <td>
          {editing ? (
            <label className="buque-rule-switch">
              <input
                type="checkbox"
                checked={draft.is_enabled}
                onChange={(e) => setDraft((d) => ({ ...d, is_enabled: e.target.checked }))}
              />
              <span>{draft.is_enabled ? '已启用' : '已停用'}</span>
            </label>
          ) : (
            <RuleEnableStatus enabled={rule.is_enabled} />
          )}
        </td>
        <td className="whitespace-nowrap text-xs text-[var(--sea-ink-soft)]">v{rule.version}</td>
        <td className="whitespace-nowrap text-xs text-[var(--sea-ink-soft)]">{rule.effective_date}</td>
        <td className="whitespace-nowrap">
          <div className="flex flex-wrap items-center gap-2">
            {editing ? (
              <>
                <button
                  type="button"
                  className="demo-button demo-button-sm"
                  disabled={!dirty || !reason.trim() || mutation.isPending}
                  onClick={() => mutation.mutate()}
                >
                  {mutation.isPending ? '保存中…' : '保存'}
                </button>
                <button
                  type="button"
                  className="demo-button demo-button-secondary demo-button-sm"
                  disabled={mutation.isPending}
                  onClick={cancelEdit}
                >
                  取消
                </button>
              </>
            ) : (
              <button
                type="button"
                className="inline-flex items-center gap-1 text-sm font-medium text-[var(--aqua)]"
                onClick={() => setEditing(true)}
              >
                <Pencil size={14} />
                编辑
              </button>
            )}
            <button
              type="button"
              className="inline-flex items-center gap-1 text-sm font-medium text-[var(--sea-ink-soft)] hover:text-[var(--aqua)]"
              onClick={() => setHistoryOpen(true)}
            >
              <History size={14} />
              历史
            </button>
          </div>
        </td>
      </tr>

      {editing ? (
        <tr className="buque-rule-expand-row">
          <td colSpan={8}>
            <div className="buque-rule-save-bar">
              <span className="text-xs text-[var(--sea-ink-soft)]">变更原因（必填）</span>
              <input
                className="demo-input min-w-[14rem] flex-1"
                placeholder="说明本次调整的业务原因"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              {mutation.error ? (
                <span className="text-xs text-[var(--status-danger)]">
                  {(mutation.error as Error).message}
                </span>
              ) : null}
            </div>
          </td>
        </tr>
      ) : null}

      <RuleHistoryModal rule={rule} open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </Fragment>
  )
}

type Props = {
  rules: RuleTableRow[]
  focus?: string
}

export function RulesTable({ rules, focus }: Props) {
  return (
    <section className="buque-table-panel min-w-0">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--sea-ink)]">规则配置列表</h2>
        <span className="text-xs text-[var(--sea-ink-soft)]">共 {rules.length} 条</span>
      </div>

      <div className="buque-alerts-table-wrap">
        <table className="buque-alerts-table">
          <thead>
            <tr>
              <th>分类</th>
              <th>判断规则</th>
              <th>说明</th>
              <th>参数值</th>
              <th>状态</th>
              <th>版本</th>
              <th>生效日</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <RuleRow key={rule.rule_code} rule={rule} focused={focus === rule.rule_code} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

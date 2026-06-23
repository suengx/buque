import { ChevronDown, Database, RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSnapshot } from '#/context/SnapshotContext'
import { usePipeline } from '#/hooks/usePipeline'
import type { SnapshotSummary } from '#/lib/api'
import { cn } from '#/lib/utils'

const TZ = 'Asia/Shanghai'

function formatShanghai(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', {
    timeZone: TZ,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatNextRun(iso: string) {
  const run = new Date(iso)
  const now = new Date()
  const runDay = run.toLocaleDateString('zh-CN', { timeZone: TZ })
  const today = now.toLocaleDateString('zh-CN', { timeZone: TZ })
  const time = run.toLocaleString('zh-CN', {
    timeZone: TZ,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  if (runDay === today) return `今日 ${time}`
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowDay = tomorrow.toLocaleDateString('zh-CN', { timeZone: TZ })
  if (runDay === tomorrowDay) return `明日 ${time}`
  return formatShanghai(iso)
}

function formatSyncCounts(latest: SnapshotSummary | undefined) {
  if (!latest?.sync_summary) return null
  const counts = latest.sync_summary.ingestion_counts as Record<string, number> | undefined
  if (!counts) return null
  return `库存 ${counts.inventory ?? 0} / 订单 ${counts.orders ?? 0} / TMS ${counts.inbound ?? 0} 行`
}

function triggerSubtext(
  latest: SnapshotSummary | undefined,
  active: boolean,
  statusHint: string | null,
) {
  if (active) {
    if (statusHint) return statusHint
    return '同步并分析中'
  }
  if (latest?.finished_at) {
    return `上次 ${formatShanghai(latest.finished_at)}`
  }
  return '暂无流水线记录'
}

export function DataOpsHub({ embedded = false }: { embedded?: boolean }) {
  const { selectedSnapshot, snapshots } = useSnapshot()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const { opsStatus, pipelineBusy, statusHint, startPipeline } = usePipeline()

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  const latest = selectedSnapshot ?? snapshots[0]
  const counts = formatSyncCounts(latest)
  const subtext = triggerSubtext(latest, pipelineBusy, statusHint)
  const statusLabel = pipelineBusy ? '执行中' : '空闲'

  return (
    <div ref={rootRef} className={cn('buque-ops-hub', embedded && 'buque-ops-hub-embedded')}>
      <button
        type="button"
        className={cn(
          'buque-ops-trigger',
          embedded && 'buque-ops-trigger-embedded',
          pipelineBusy && 'buque-ops-trigger-active',
        )}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={cn('buque-ops-icon-wrap', pipelineBusy && 'buque-ops-wave')}>
          {pipelineBusy ? (
            <RefreshCw size={14} className="buque-ops-icon-spin" />
          ) : (
            <Database size={14} />
          )}
        </span>
        <span className="buque-ops-trigger-text">
          <span className="buque-ops-trigger-label">数据同步</span>
          <span className="buque-ops-trigger-sub">{subtext}</span>
        </span>
        <ChevronDown size={14} className={cn('buque-ops-chevron', open && 'buque-ops-chevron-open')} />
      </button>

      {open ? (
        <div className="buque-ops-panel">
          <section className="buque-ops-section">
            <h3 className="buque-ops-section-title">任务状态</h3>
            <div className="buque-ops-status-row">
              <span
                className={cn(
                  'buque-ops-dot',
                  pipelineBusy ? 'buque-ops-dot-active' : 'buque-ops-dot-idle',
                )}
              />
              <div className="min-w-0">
                <p className="buque-ops-status-main">{statusLabel}</p>
                {pipelineBusy && statusHint ? (
                  <p className="buque-ops-status-sub">{statusHint}</p>
                ) : (
                  <p className="buque-ops-status-sub">当前无后台任务运行</p>
                )}
              </div>
            </div>
          </section>

          <section className="buque-ops-section">
            <h3 className="buque-ops-section-title">定时计划</h3>
            <p className="buque-ops-line">
              {opsStatus?.schedule_label ?? '每日 06:00'} 自动同步并分析
            </p>
            <p className="buque-ops-line-muted">
              下次执行：
              {opsStatus?.next_scheduled_at
                ? formatNextRun(opsStatus.next_scheduled_at)
                : '—'}
              <span className="mx-1">·</span>
              {opsStatus?.timezone ?? TZ}
            </p>
          </section>

          <section className="buque-ops-section">
            <h3 className="buque-ops-section-title">最近快照</h3>
            {latest?.finished_at ? (
              <>
                <p className="buque-ops-line">完成于 {formatShanghai(latest.finished_at)}</p>
                <p className="buque-ops-line-muted">业务日 {latest.monitor_date}</p>
                {counts ? <p className="buque-ops-line-muted">{counts}</p> : null}
              </>
            ) : (
              <p className="buque-ops-line-muted">暂无成功快照</p>
            )}
          </section>

          <div className="buque-ops-actions">
            <button
              type="button"
              className="demo-button demo-button-sm w-full"
              disabled={pipelineBusy || !opsStatus?.erp_configured}
              onClick={() => startPipeline()}
              title={opsStatus?.erp_configured ? undefined : 'ERP 未配置'}
            >
              {pipelineBusy ? '同步并分析中…' : '同步并分析'}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

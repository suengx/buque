import { Camera, ChevronDown } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { DataOpsHub } from '#/components/buque/DataOpsHub'
import { useSnapshot } from '#/context/SnapshotContext'
import { cn } from '#/lib/utils'

const TZ = 'Asia/Shanghai'

function formatSnapshotTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', {
    timeZone: TZ,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function snapshotLabel(snapshot: { monitor_date: string; finished_at: string | null }) {
  const time = snapshot.finished_at ? formatSnapshotTime(snapshot.finished_at) : '进行中'
  return `${time} · 业务日 ${snapshot.monitor_date}`
}

type SnapshotSelectorProps = {
  embedded?: boolean
  onSnapshotSelect?: (snapshotId: number) => void
}

export function SnapshotSelector({ embedded = false, onSnapshotSelect }: SnapshotSelectorProps) {
  const { snapshots, selectedSnapshotId, selectedSnapshot, setSelectedSnapshotId, isLoading } =
    useSnapshot()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

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

  const label = selectedSnapshot
    ? snapshotLabel(selectedSnapshot)
    : isLoading
      ? '加载快照…'
      : '暂无快照'

  return (
    <div ref={rootRef} className={cn('buque-monitor-date', embedded && 'buque-monitor-date-embedded')}>
      <button
        type="button"
        className="buque-snapshot-trigger"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="buque-monitor-date-icon">
          <Camera size={14} />
        </span>
        <span className="buque-monitor-date-text">
          <span className="buque-monitor-date-label">数据快照</span>
          <span className="buque-snapshot-value">{label}</span>
        </span>
        <ChevronDown size={14} className={cn('buque-ops-chevron', open && 'buque-ops-chevron-open')} />
      </button>

      {open ? (
        <div className="buque-snapshot-menu">
          {snapshots.length === 0 ? (
            <p className="buque-snapshot-empty">暂无成功快照，请先运行同步并分析</p>
          ) : (
            snapshots.map((s) => (
              <button
                key={s.id}
                type="button"
                className={cn(
                  'buque-snapshot-option',
                  s.id === selectedSnapshotId && 'buque-snapshot-option-active',
                )}
                onClick={() => {
                  setSelectedSnapshotId(s.id)
                  onSnapshotSelect?.(s.id)
                  setOpen(false)
                }}
              >
                {snapshotLabel(s)}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}

type ContextDockProps = {
  placement?: 'fixed' | 'inline'
  onSnapshotSelect?: (snapshotId: number) => void
}

export function ContextDock({ placement = 'fixed', onSnapshotSelect }: ContextDockProps) {
  return (
    <div
      className={cn(
        'buque-context-dock',
        placement === 'inline' && 'buque-context-dock-inline',
      )}
      aria-label="数据快照与同步"
    >
      <SnapshotSelector embedded onSnapshotSelect={onSnapshotSelect} />
      <div className="buque-context-dock-divider" aria-hidden />
      <DataOpsHub embedded />
    </div>
  )
}

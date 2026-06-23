import { Calendar } from 'lucide-react'
import { DataOpsHub } from '#/components/buque/DataOpsHub'
import { useMonitorDate } from '#/context/MonitorDateContext'
import { cn } from '#/lib/utils'

export function MonitorDatePicker({ embedded = false }: { embedded?: boolean }) {
  const { monitorDate, setMonitorDate } = useMonitorDate()
  return (
    <label className={cn('buque-monitor-date', embedded && 'buque-monitor-date-embedded')}>
      <span className="buque-monitor-date-icon">
        <Calendar size={14} />
      </span>
      <span className="buque-monitor-date-text">
        <span className="buque-monitor-date-label">监控日</span>
        <input
          type="date"
          className="buque-monitor-date-input"
          value={monitorDate ?? ''}
          onChange={(e) => setMonitorDate(e.target.value || undefined)}
        />
      </span>
    </label>
  )
}

export function ContextDock() {
  return (
    <div className="buque-context-dock" aria-label="监控日与数据同步">
      <MonitorDatePicker embedded />
      <div className="buque-context-dock-divider" aria-hidden />
      <DataOpsHub embedded />
    </div>
  )
}

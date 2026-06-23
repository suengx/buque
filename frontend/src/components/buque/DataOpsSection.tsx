import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  api,
  queryKeys,
  type AnalysisStatusResponse,
  type ErpSyncLatestResponse,
  type ErpSyncStatusResponse,
} from '#/lib/api'

type Props = {
  monitorDate?: string
}

const SOURCE_LABELS: Record<string, string> = {
  erp_inventory: '产品库存',
  erp_orders: '全渠道订单',
  tms_inbound: 'TMS 在途',
}

const SYNC_PHASE_LABELS: Record<string, string> = {
  EXPORTING: '正在从积加导出数据…',
  INGESTING: '正在写入数据库…',
  DONE: '同步完成',
}

const ANALYSIS_PHASE_LABELS: Record<string, string> = {
  QUALITY: '数据质量检查',
  RULES: '规则计算',
  EVENTS: '构建事件池',
  EXPLAIN: '生成解释',
  DONE: '分析完成',
}

function SourceRow({ item }: { item: ErpSyncStatusResponse['sources'][number] }) {
  const label = SOURCE_LABELS[item.source] ?? item.source
  const statusClass =
    item.status === 'SUCCESS'
      ? 'text-[var(--status-success)]'
      : item.status === 'FAILED'
        ? 'text-[var(--status-danger)]'
        : item.status === 'RUNNING' || item.status === 'EXPORTING' || item.status === 'INGESTING'
          ? 'text-[var(--status-warning)]'
          : 'demo-muted'
  const statusText =
    item.status === 'EXPORTING'
      ? '导出中'
      : item.status === 'INGESTING'
        ? '落库中'
        : item.status === 'PENDING'
          ? '等待中'
          : item.status
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--line)] py-2 text-sm last:border-0">
      <div>
        <div className="font-medium text-[var(--sea-ink)]">{label}</div>
        <div className={statusClass}>
          {statusText}
          {item.status === 'SUCCESS' ? ` · ${item.row_count} 行` : ''}
        </div>
        {item.error ? <div className="mt-1 text-xs text-[var(--status-danger)]">{item.error}</div> : null}
      </div>
    </div>
  )
}

function LogList({ logs }: { logs: { level: string; message: string; created_at: string }[] }) {
  if (!logs.length) return null
  return (
    <div className="buque-log-list mt-2 max-h-32 overflow-y-auto rounded-lg p-2 font-mono text-xs">
      {logs.map((log, i) => (
        <div
          key={`${log.created_at}-${i}`}
          className={log.level === 'ERROR' ? 'text-[var(--status-danger)]' : 'demo-muted'}
        >
          {log.message}
        </div>
      ))}
    </div>
  )
}

function formatSyncSummary(latest: ErpSyncLatestResponse | undefined) {
  if (!latest?.has_sync || !latest.sync_summary) return null
  const counts = latest.sync_summary.ingestion_counts as Record<string, number> | undefined
  if (!counts) return null
  return `库存 ${counts.inventory ?? 0} / 订单 ${counts.orders ?? 0} / TMS ${counts.inbound ?? 0} 行`
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function freshnessText(latest: ErpSyncLatestResponse | undefined) {
  if (!latest?.has_sync) return '暂无同步记录'
  const summary = formatSyncSummary(latest)
  const time = formatTime(latest.finished_at)
  return summary ? `上次同步于 ${time} · ${summary}` : `上次同步于 ${time}`
}

export function DataOpsSection({ monitorDate }: Props) {
  const qc = useQueryClient()
  const [syncStatus, setSyncStatus] = useState<ErpSyncStatusResponse | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatusResponse | null>(null)
  const [syncJobId, setSyncJobId] = useState<number | null>(null)
  const [analysisJobId, setAnalysisJobId] = useState<number | null>(null)
  const [syncPolling, setSyncPolling] = useState(false)
  const [analysisPolling, setAnalysisPolling] = useState(false)

  const latestQuery = useQuery({
    queryKey: ['syncLatest', monitorDate],
    queryFn: () => api.getErpSyncLatest(monitorDate),
    enabled: !!monitorDate,
  })

  const syncMutation = useMutation({
    mutationFn: () => api.startErpSync({ monitorDate }),
    onSuccess: (data) => {
      setSyncStatus(null)
      setSyncJobId(data.job_id)
      setSyncPolling(true)
    },
  })

  const analysisMutation = useMutation({
    mutationFn: () => api.startAnalysis({ monitorDate }),
    onSuccess: (data) => {
      setAnalysisStatus(null)
      setAnalysisJobId(data.job_id)
      setAnalysisPolling(true)
    },
  })

  useEffect(() => {
    if (!monitorDate) return
    let cancelled = false
    const probe = async () => {
      try {
        const s = await api.getErpSyncStatus(monitorDate)
        if (cancelled) return
        if (s.running && s.job_id) {
          setSyncStatus(s)
          setSyncJobId(s.job_id)
          setSyncPolling(true)
        }
      } catch {
        /* ignore probe errors */
      }
    }
    probe()
    return () => {
      cancelled = true
    }
  }, [monitorDate])

  useEffect(() => {
    if (!monitorDate) return
    let cancelled = false
    const probe = async () => {
      try {
        const s = await api.getAnalysisStatus(monitorDate)
        if (cancelled) return
        if (s.running && s.job_id) {
          setAnalysisStatus(s)
          setAnalysisJobId(s.job_id)
          setAnalysisPolling(true)
        }
      } catch {
        /* ignore probe errors */
      }
    }
    probe()
    return () => {
      cancelled = true
    }
  }, [monitorDate])

  useEffect(() => {
    if (!syncPolling || syncJobId === null) return
    let cancelled = false
    const tick = async () => {
      try {
        const s = await api.getErpSyncStatus(monitorDate, syncJobId)
        if (cancelled) return
        setSyncStatus(s)
        if (s.job_status === 'SUCCESS' || s.job_status === 'FAILED') {
          setSyncPolling(false)
          if (s.job_status === 'SUCCESS') {
            await qc.invalidateQueries({ queryKey: ['syncLatest', monitorDate] })
          }
        }
      } catch {
        if (!cancelled) setSyncPolling(false)
      }
    }
    tick()
    const id = window.setInterval(tick, 2000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [syncPolling, monitorDate, syncJobId, qc])

  useEffect(() => {
    if (!analysisPolling || analysisJobId === null) return
    let cancelled = false
    const tick = async () => {
      try {
        const s = await api.getAnalysisStatus(monitorDate, analysisJobId)
        if (cancelled) return
        setAnalysisStatus(s)
        if (s.job_status === 'SUCCESS' || s.job_status === 'FAILED') {
          setAnalysisPolling(false)
          if (s.job_status === 'SUCCESS') {
            await qc.invalidateQueries({ queryKey: queryKeys.dailyReport(monitorDate) })
            await qc.invalidateQueries({ queryKey: ['alerts'] })
          }
        }
      } catch {
        if (!cancelled) setAnalysisPolling(false)
      }
    }
    tick()
    const id = window.setInterval(tick, 2000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [analysisPolling, monitorDate, analysisJobId, qc])

  const syncBusy = syncMutation.isPending || syncPolling
  const analysisBusy = analysisMutation.isPending || analysisPolling
  const syncDone = syncStatus?.job_status === 'SUCCESS'
  const syncFailed = syncStatus?.job_status === 'FAILED'
  const analysisDone = analysisStatus?.job_status === 'SUCCESS'
  const analysisFailed = analysisStatus?.job_status === 'FAILED'
  const currentSyncSummary = syncStatus?.sync_summary
    ? formatSyncSummary({
        monitor_date: syncStatus.monitor_date,
        has_sync: true,
        sync_summary: syncStatus.sync_summary,
      })
    : null

  return (
    <div className="space-y-3">
      <p className="text-sm demo-muted">数据新鲜度：{freshnessText(latestQuery.data)}</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="demo-panel">
          <h2 className="demo-section-title">数据同步</h2>
          {syncBusy && syncStatus?.phase ? (
            <div className="mt-2 flex items-center gap-2 text-sm text-[var(--status-warning)]">
              <span className="buque-spinner" />
              {syncStatus.phase_message ?? SYNC_PHASE_LABELS[syncStatus.phase]}
            </div>
          ) : null}
          {syncDone ? (
            <div className="demo-alert demo-alert-success mt-2 text-sm">
              同步完成{currentSyncSummary ? `：${currentSyncSummary}` : ''}
            </div>
          ) : null}
          {syncFailed ? (
            <div className="demo-alert demo-alert-danger mt-2 text-sm">
              同步失败：{syncStatus?.error ?? '未知错误'}
            </div>
          ) : null}
          {syncMutation.error ? (
            <div className="demo-alert demo-alert-danger mt-2 text-sm">
              {String(syncMutation.error.message)}
            </div>
          ) : null}
          {syncStatus ? (
            <div className="demo-card mt-3">
              {syncStatus.sources.map((s) => (
                <SourceRow key={s.source} item={s} />
              ))}
              <LogList logs={syncStatus.logs} />
            </div>
          ) : syncBusy ? (
            <div className="demo-card mt-3 text-sm demo-muted">任务已启动，等待状态…</div>
          ) : null}
          <button
            type="button"
            className="demo-button mt-3"
            disabled={syncBusy}
            onClick={() => syncMutation.mutate()}
          >
            {syncBusy ? '同步中…' : '开始同步'}
          </button>
        </section>

        <section className="demo-panel">
          <h2 className="demo-section-title">规则分析</h2>
          <p className="mt-1 text-xs demo-muted">
            基于当前库内数据 · 数据质量检查 → 规则计算 → 事件池 → 解释生成
          </p>
          {analysisBusy && analysisStatus?.phase ? (
            <div className="mt-2 flex items-center gap-2 text-sm text-[var(--status-warning)]">
              <span className="buque-spinner" />
              {analysisStatus.phase_message ??
                ANALYSIS_PHASE_LABELS[analysisStatus.phase] ??
                analysisStatus.phase}
            </div>
          ) : null}
          {analysisDone && analysisStatus?.analysis_summary ? (
            <div className="demo-alert demo-alert-success mt-2 text-sm">
              分析完成：质量 {analysisStatus.analysis_summary.quality_issues} / 规则{' '}
              {analysisStatus.analysis_summary.monitor_results} / 事件{' '}
              {analysisStatus.analysis_summary.events} / 解释{' '}
              {analysisStatus.analysis_summary.explained}
            </div>
          ) : null}
          {analysisFailed ? (
            <div className="demo-alert demo-alert-danger mt-2 text-sm">
              分析失败：{analysisStatus?.error ?? '未知错误'}
            </div>
          ) : null}
          {analysisMutation.error ? (
            <div className="demo-alert demo-alert-danger mt-2 text-sm">
              {String(analysisMutation.error.message)}
            </div>
          ) : null}
          {analysisStatus?.logs?.length ? <LogList logs={analysisStatus.logs} /> : null}
          <button
            type="button"
            className="demo-button mt-3"
            disabled={analysisBusy}
            onClick={() => analysisMutation.mutate()}
          >
            {analysisBusy ? '分析中…' : '运行分析'}
          </button>
        </section>
      </div>
    </div>
  )
}

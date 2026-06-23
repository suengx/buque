import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  api,
  queryKeys,
  type AnalysisStatusResponse,
  type ErpSyncStatusResponse,
  type OpsStatusResponse,
} from '#/lib/api'

export function useDataOps(monitorDate?: string) {
  const qc = useQueryClient()
  const [syncStatus, setSyncStatus] = useState<ErpSyncStatusResponse | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatusResponse | null>(null)
  const [syncJobId, setSyncJobId] = useState<number | null>(null)
  const [analysisJobId, setAnalysisJobId] = useState<number | null>(null)
  const [syncPolling, setSyncPolling] = useState(false)
  const [analysisPolling, setAnalysisPolling] = useState(false)

  const { data: opsStatus, refetch: refetchOps } = useQuery({
    queryKey: queryKeys.opsStatus(monitorDate),
    queryFn: () => api.getOpsStatus(monitorDate),
    enabled: !!monitorDate,
    refetchInterval: (query) => {
      const data = query.state.data as OpsStatusResponse | undefined
      return data?.pipeline_active || syncPolling || analysisPolling ? 2000 : 8000
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.startErpSync({ monitorDate }),
    onSuccess: (data) => {
      setSyncStatus(null)
      setSyncJobId(data.job_id)
      setSyncPolling(true)
      void refetchOps()
    },
  })

  const analysisMutation = useMutation({
    mutationFn: () => api.startAnalysis({ monitorDate }),
    onSuccess: (data) => {
      setAnalysisStatus(null)
      setAnalysisJobId(data.job_id)
      setAnalysisPolling(true)
      void refetchOps()
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
        /* ignore */
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
        /* ignore */
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
        void refetchOps()
        if (s.job_status === 'SUCCESS' || s.job_status === 'FAILED') {
          setSyncPolling(false)
          if (s.job_status === 'SUCCESS') {
            await qc.invalidateQueries({ queryKey: queryKeys.opsStatus(monitorDate) })
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
  }, [syncPolling, monitorDate, syncJobId, qc, refetchOps])

  useEffect(() => {
    if (!analysisPolling || analysisJobId === null) return
    let cancelled = false
    const tick = async () => {
      try {
        const s = await api.getAnalysisStatus(monitorDate, analysisJobId)
        if (cancelled) return
        setAnalysisStatus(s)
        void refetchOps()
        if (s.job_status === 'SUCCESS' || s.job_status === 'FAILED') {
          setAnalysisPolling(false)
          if (s.job_status === 'SUCCESS') {
            await qc.invalidateQueries({ queryKey: queryKeys.dailyReport(monitorDate) })
            await qc.invalidateQueries({ queryKey: queryKeys.reportAnalytics(monitorDate) })
            await qc.invalidateQueries({ queryKey: ['alerts'] })
            await qc.invalidateQueries({ queryKey: queryKeys.opsStatus(monitorDate) })
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
  }, [analysisPolling, monitorDate, analysisJobId, qc, refetchOps])

  const syncBusy = syncMutation.isPending || syncPolling || Boolean(opsStatus?.sync_running)
  const analysisBusy =
    analysisMutation.isPending || analysisPolling || Boolean(opsStatus?.analysis_running)
  const pipelineActive = syncBusy || analysisBusy

  const statusHint = (() => {
    if (syncBusy && syncStatus?.phase_message) return syncStatus.phase_message
    if (analysisBusy && analysisStatus?.phase_message) return analysisStatus.phase_message
    if (opsStatus?.sync_running && opsStatus.sync_phase_message) return opsStatus.sync_phase_message
    if (opsStatus?.analysis_running && opsStatus.analysis_phase_message) {
      return opsStatus.analysis_phase_message
    }
    if (syncStatus?.job_status === 'FAILED') return `同步失败：${syncStatus.error ?? '未知错误'}`
    if (analysisStatus?.job_status === 'FAILED') {
      return `分析失败：${analysisStatus.error ?? '未知错误'}`
    }
    return null
  })()

  return {
    opsStatus,
    syncBusy,
    analysisBusy,
    pipelineActive,
    statusHint,
    startSync: () => syncMutation.mutate(),
    startAnalysis: () => analysisMutation.mutate(),
    syncError: syncMutation.error,
    analysisError: analysisMutation.error,
  }
}

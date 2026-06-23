import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, queryKeys, type PipelineStatusResponse } from '#/lib/api'
import { useSnapshot } from '#/context/SnapshotContext'

export function usePipeline() {
  const qc = useQueryClient()
  const { setSelectedSnapshotId, refetchSnapshots } = useSnapshot()
  const [jobId, setJobId] = useState<number | null>(null)
  const [polling, setPolling] = useState(false)
  const [status, setStatus] = useState<PipelineStatusResponse | null>(null)

  const { data: opsStatus, refetch: refetchOps } = useQuery({
    queryKey: queryKeys.opsStatus,
    queryFn: () => api.getOpsStatus(),
    refetchInterval: (query) => {
      const active = query.state.data?.pipeline_active || polling
      return active ? 2000 : 8000
    },
  })

  const mutation = useMutation({
    mutationFn: (monitorDate?: string) => api.startPipeline({ monitorDate }),
    onSuccess: (data) => {
      setStatus(null)
      setJobId(data.snapshot_id)
      setPolling(true)
      void refetchOps()
    },
  })

  useEffect(() => {
    if (!polling || jobId === null) return
    let cancelled = false
    const tick = async () => {
      try {
        const s = await api.getPipelineStatus(jobId)
        if (cancelled) return
        setStatus(s)
        void refetchOps()
        if (s.job_status === 'SUCCESS' || s.job_status === 'FAILED') {
          setPolling(false)
          if (s.job_status === 'SUCCESS' && s.snapshot_id) {
            await qc.invalidateQueries({ queryKey: queryKeys.snapshots })
            refetchSnapshots()
            setSelectedSnapshotId(s.snapshot_id)
            const sid = s.snapshot_id
            await qc.invalidateQueries({ queryKey: queryKeys.dailyReport(sid) })
            await qc.invalidateQueries({ queryKey: queryKeys.reportAnalytics(sid) })
            await qc.invalidateQueries({ queryKey: ['alerts'] })
          }
        }
      } catch {
        if (!cancelled) setPolling(false)
      }
    }
    tick()
    const id = window.setInterval(tick, 2000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [polling, jobId, qc, refetchOps, refetchSnapshots, setSelectedSnapshotId])

  useEffect(() => {
    if (opsStatus?.pipeline_active && opsStatus.running_snapshot_id && !polling) {
      setJobId(opsStatus.running_snapshot_id)
      setPolling(true)
    }
  }, [opsStatus?.pipeline_active, opsStatus?.running_snapshot_id, polling])

  const pipelineBusy = mutation.isPending || polling || Boolean(opsStatus?.pipeline_active)
  const statusHint =
    (polling && status?.phase_message) ||
    opsStatus?.phase_message ||
    (status?.job_status === 'FAILED' ? status.error : null)

  return {
    opsStatus,
    pipelineBusy,
    statusHint,
    startPipeline: (monitorDate?: string) => mutation.mutate(monitorDate),
    pipelineError: mutation.error,
  }
}

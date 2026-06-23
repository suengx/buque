import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, queryKeys, type SnapshotSummary } from '#/lib/api'

type SnapshotContextValue = {
  snapshots: SnapshotSummary[]
  selectedSnapshotId: number | undefined
  selectedSnapshot: SnapshotSummary | undefined
  setSelectedSnapshotId: (id: number | undefined) => void
  isLoading: boolean
  refetchSnapshots: () => void
}

const SnapshotContext = createContext<SnapshotContextValue | null>(null)

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | undefined>(undefined)
  const { data: snapshots = [], isLoading, refetch } = useQuery({
    queryKey: queryKeys.snapshots,
    queryFn: () => api.listSnapshots(),
  })

  const effectiveId = selectedSnapshotId ?? snapshots[0]?.id

  const selectedSnapshot = useMemo(
    () => snapshots.find((s) => s.id === effectiveId),
    [snapshots, effectiveId],
  )

  const value = useMemo(
    () => ({
      snapshots,
      selectedSnapshotId: effectiveId,
      selectedSnapshot,
      setSelectedSnapshotId,
      isLoading,
      refetchSnapshots: () => {
        void refetch()
      },
    }),
    [snapshots, effectiveId, selectedSnapshot, isLoading, refetch],
  )

  return <SnapshotContext.Provider value={value}>{children}</SnapshotContext.Provider>
}

export function useSnapshot() {
  const ctx = useContext(SnapshotContext)
  if (!ctx) throw new Error('useSnapshot must be used within SnapshotProvider')
  return ctx
}

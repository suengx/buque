import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

type MonitorDateContextValue = {
  monitorDate: string | undefined
  setMonitorDate: (date: string | undefined) => void
}

const MonitorDateContext = createContext<MonitorDateContextValue | null>(null)

export function MonitorDateProvider({ children }: { children: ReactNode }) {
  const [monitorDate, setMonitorDate] = useState<string | undefined>(undefined)
  const value = useMemo(() => ({ monitorDate, setMonitorDate }), [monitorDate])
  return <MonitorDateContext.Provider value={value}>{children}</MonitorDateContext.Provider>
}

export function useMonitorDate() {
  const ctx = useContext(MonitorDateContext)
  if (!ctx) throw new Error('useMonitorDate must be used within MonitorDateProvider')
  return ctx
}

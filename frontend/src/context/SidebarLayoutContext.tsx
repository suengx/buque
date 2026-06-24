import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

const STORAGE_KEY = 'buque.sidebar.collapsed'

type SidebarLayoutContextValue = {
  collapsed: boolean
  toggleCollapsed: () => void
}

const SidebarLayoutContext = createContext<SidebarLayoutContextValue | null>(null)

function readStoredCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) === 'true'
}

export function SidebarLayoutProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(readStoredCollapsed)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed))
    document.documentElement.dataset.sidebarCollapsed = collapsed ? 'true' : 'false'
  }, [collapsed])

  const toggleCollapsed = useCallback(() => {
    setCollapsed((value) => !value)
  }, [])

  const value = useMemo(
    () => ({ collapsed, toggleCollapsed }),
    [collapsed, toggleCollapsed],
  )

  return (
    <SidebarLayoutContext.Provider value={value}>{children}</SidebarLayoutContext.Provider>
  )
}

export function useSidebarLayout() {
  const ctx = useContext(SidebarLayoutContext)
  if (!ctx) throw new Error('useSidebarLayout must be used within SidebarLayoutProvider')
  return ctx
}

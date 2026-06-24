import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { authApi, type AuthUser } from '#/lib/auth-api'
import { AUTH_TOKEN_KEY, clearAuthToken, getAuthToken, setAuthToken } from '#/lib/auth-token'

type AuthContextValue = {
  token: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (accessToken: string, user: AuthUser) => void
  logout: () => void
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getAuthToken())
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(() => !!getAuthToken())

  const login = useCallback((accessToken: string, nextUser: AuthUser) => {
    setAuthToken(accessToken)
    setToken(accessToken)
    setUser(nextUser)
  }, [])

  const logout = useCallback(() => {
    clearAuthToken()
    setToken(null)
    setUser(null)
  }, [])

  const refreshMe = useCallback(async () => {
    const current = getAuthToken()
    if (!current) {
      setUser(null)
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    try {
      const profile = await authApi.me()
      setToken(current)
      setUser(profile)
    } catch {
      logout()
    } finally {
      setIsLoading(false)
    }
  }, [logout])

  useEffect(() => {
    if (token) {
      void refreshMe()
    } else {
      setIsLoading(false)
    }
  }, [token, refreshMe])

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: !!token,
      isLoading,
      login,
      logout,
      refreshMe,
    }),
    [token, user, isLoading, login, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}

export { AUTH_TOKEN_KEY }

import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router'
import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { AuthSplitLayout } from '#/components/auth/AuthSplitLayout'
import { useAuth } from '#/context/AuthContext'
import { authApi } from '#/lib/auth-api'
import { AUTH_TOKEN_KEY } from '#/lib/auth-token'

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''
const passwordEnabled =
  !googleClientId || import.meta.env.VITE_AUTH_PASSWORD_ENABLED === 'true'

type LoginSearch = {
  redirect?: string
}

export const Route = createFileRoute('/login/')({
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
  }),
  beforeLoad: () => {
    if (typeof window !== 'undefined' && localStorage.getItem(AUTH_TOKEN_KEY)) {
      throw redirect({ to: '/' })
    }
  },
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { redirect: redirectTo } = Route.useSearch()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const goAfterLogin = () => {
    if (redirectTo && typeof window !== 'undefined') {
      try {
        const url = new URL(redirectTo, window.location.origin)
        if (url.origin === window.location.origin) {
          void navigate({ to: `${url.pathname}${url.search}` as '/' })
          return
        }
      } catch {
        /* fall through */
      }
    }
    void navigate({ to: '/' })
  }

  const handleAuthSuccess = (accessToken: string, user: Parameters<typeof login>[1]) => {
    login(accessToken, user)
    goAfterLogin()
  }

  const handlePasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    if (mode === 'register' && password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    setSubmitting(true)
    try {
      const result =
        mode === 'login'
          ? await authApi.login(email, password)
          : await authApi.register(email, password)
      handleAuthSuccess(result.access_token, result.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  const form = (
    <div className="auth-form-card">
      <h2 className="auth-form-title">登录补雀</h2>

      {googleClientId ? (
        <>
          <div className="auth-google-wrap">
            <GoogleLogin
              onSuccess={async (response) => {
                if (!response.credential) return
                setError(null)
                setSubmitting(true)
                try {
                  const result = await authApi.google(response.credential)
                  handleAuthSuccess(result.access_token, result.user)
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Google 登录失败')
                } finally {
                  setSubmitting(false)
                }
              }}
              onError={() => setError('Google 登录失败')}
              theme="outline"
              size="large"
              text="signin_with"
              locale="zh_CN"
              width="100%"
            />
          </div>
          {passwordEnabled ? <div className="auth-divider">或</div> : null}
        </>
      ) : null}

      {passwordEnabled ? (
        <>
          <div className="auth-tabs">
            <button
              type="button"
              className={mode === 'login' ? 'auth-tab active' : 'auth-tab'}
              onClick={() => setMode('login')}
            >
              登录
            </button>
            <button
              type="button"
              className={mode === 'register' ? 'auth-tab active' : 'auth-tab'}
              onClick={() => setMode('register')}
            >
              注册
            </button>
          </div>
          <form className="auth-form" onSubmit={handlePasswordSubmit}>
            <label className="auth-field">
              <span>邮箱</span>
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="auth-field">
              <span>密码</span>
              <input
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {mode === 'register' ? (
              <label className="auth-field">
                <span>确认密码</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </label>
            ) : null}
            {error ? <p className="auth-error">{error}</p> : null}
            <button type="submit" className="demo-button auth-submit" disabled={submitting}>
              {submitting ? '处理中…' : mode === 'login' ? '登录' : '注册'}
            </button>
          </form>
        </>
      ) : error ? (
        <p className="auth-error">{error}</p>
      ) : null}
    </div>
  )

  return (
    <AuthSplitLayout>
      {googleClientId ? (
        <GoogleOAuthProvider clientId={googleClientId}>{form}</GoogleOAuthProvider>
      ) : (
        form
      )}
    </AuthSplitLayout>
  )
}

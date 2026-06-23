import { useEffect, useState } from 'react'
import { applyThemeMode, getInitialMode, type ThemeMode } from '#/lib/theme'

export default function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>('light')

  useEffect(() => {
    const initialMode = getInitialMode()
    setMode(initialMode)
    applyThemeMode(initialMode)
  }, [])

  useEffect(() => {
    if (mode !== 'auto') {
      return
    }

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyThemeMode('auto')

    media.addEventListener('change', onChange)
    return () => {
      media.removeEventListener('change', onChange)
    }
  }, [mode])

  function toggleMode() {
    const nextMode: ThemeMode =
      mode === 'light' ? 'dark' : mode === 'dark' ? 'auto' : 'light'
    setMode(nextMode)
    applyThemeMode(nextMode)
    window.localStorage.setItem('theme', nextMode)
  }

  const label =
    mode === 'auto'
      ? '主题：跟随系统。点击切换为浅色。'
      : mode === 'dark'
        ? '主题：深色。点击切换为自动。'
        : '主题：浅色。点击切换为深色。'

  return (
    <button
      type="button"
      onClick={toggleMode}
      aria-label={label}
      title={label}
      className="demo-button-secondary w-full"
    >
      {mode === 'auto' ? '主题：自动' : mode === 'dark' ? '主题：深色' : '主题：浅色'}
    </button>
  )
}

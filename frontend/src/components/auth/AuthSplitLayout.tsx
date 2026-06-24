import type { ReactNode } from 'react'

type AuthSplitLayoutProps = {
  children: ReactNode
}

const narratives = [
  '规则负责稳定判断',
  'Agent 负责解释与建议',
  '人工反馈负责学习闭环',
]

export function AuthSplitLayout({ children }: AuthSplitLayoutProps) {
  return (
    <div className="auth-shell">
      <section className="auth-brand-panel">
        <div className="auth-brand-inner">
          <img src="/brand-mascot.png" alt="" className="auth-brand-mascot" />
          <h1 className="auth-brand-title">补雀 BuQue</h1>
          <ul className="auth-brand-narratives">
            {narratives.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="auth-brand-footnote">计划监控 · 库存与销量风险</p>
        </div>
      </section>
      <section className="auth-form-panel">{children}</section>
    </div>
  )
}

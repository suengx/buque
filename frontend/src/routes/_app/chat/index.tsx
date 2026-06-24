import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, MessageSquare, Plus, Send, X } from 'lucide-react'
import { useSnapshot } from '#/context/SnapshotContext'
import { useExpertChat } from '#/hooks/useExpertChat'
import { expertApi } from '#/lib/expert-api'

type ChatSearch = {
  snapshot_id?: number
  sku?: string
  warehouse?: string
  session_id?: number
  seed?: string
}

export const Route = createFileRoute('/_app/chat/')({
  validateSearch: (search: Record<string, unknown>): ChatSearch => ({
    snapshot_id:
      typeof search.snapshot_id === 'number'
        ? search.snapshot_id
        : search.snapshot_id
          ? Number(search.snapshot_id)
          : undefined,
    sku: typeof search.sku === 'string' ? search.sku : undefined,
    warehouse: typeof search.warehouse === 'string' ? search.warehouse : undefined,
    session_id:
      typeof search.session_id === 'number'
        ? search.session_id
        : search.session_id
          ? Number(search.session_id)
          : undefined,
    seed: typeof search.seed === 'string' ? search.seed : undefined,
  }),
  component: ChatPage,
})

function ChatPage() {
  const navigate = useNavigate()
  const search = Route.useSearch()
  const { selectedSnapshotId } = useSnapshot()
  const sessionId = search.session_id
  const [sessions, setSessions] = useState<Awaited<ReturnType<typeof expertApi.listSessions>>>([])
  const [input, setInput] = useState('')
  const [retryText, setRetryText] = useState<string | null>(null)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [sessionActionError, setSessionActionError] = useState<string | null>(null)
  const seededRef = useRef(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const snapshotId = search.snapshot_id ?? selectedSnapshotId

  const chat = useExpertChat(sessionId)

  const loadSessions = useCallback(async () => {
    try {
      const list = await expertApi.listSessions()
      setSessions(list)
    } catch {
      setSessions([])
    }
  }, [])

  useEffect(() => {
    void loadSessions()
  }, [loadSessions, sessionId, chat.messages.length])

  useEffect(() => {
    if (sessionId || !snapshotId) return
    let cancelled = false
    ;(async () => {
      const created = await expertApi.createSession({
        snapshot_id: snapshotId,
        sku: search.sku,
        warehouse: search.warehouse,
        seed: search.seed,
      })
      if (cancelled) return
      void navigate({
        to: '/chat',
        search: {
          session_id: created.id,
          snapshot_id: snapshotId,
          sku: search.sku,
          warehouse: search.warehouse,
        },
        replace: true,
      })
    })().catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sessionId, snapshotId, search.sku, search.warehouse, search.seed, navigate])

  useEffect(() => {
    if (!sessionId || seededRef.current || search.seed !== 'deep_analysis') return
    if (!search.sku) return
    seededRef.current = true
    const warehousePart = search.warehouse ? `（仓库 ${search.warehouse}）` : ''
    void chat.sendMessage(
      `请对 SKU ${search.sku}${warehousePart} 做深度分析，结合规则解释与库存销量事实，并提交可采纳的解释草稿。`,
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, search.seed, search.sku, search.warehouse])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages, chat.streamingText, chat.isSending])

  const handleNewSession = async () => {
    if (!snapshotId || isCreatingSession || chat.isSending) return
    setIsCreatingSession(true)
    setSessionActionError(null)
    chat.clearError()
    try {
      const created = await expertApi.createSession({ snapshot_id: snapshotId })
      await loadSessions()
      seededRef.current = false
      void navigate({
        to: '/chat',
        search: { session_id: created.id, snapshot_id: snapshotId },
      })
    } catch (err) {
      setSessionActionError(err instanceof Error ? err.message : '创建会话失败')
    } finally {
      setIsCreatingSession(false)
    }
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const text = input.trim()
    if (!text) return
    setInput('')
    setRetryText(text)
    chat.clearError()
    void chat.sendMessage(text)
  }

  const handleRetry = () => {
    if (!retryText) return
    chat.clearError()
    void chat.sendMessage(retryText)
    setRetryText(null)
  }

  const showEmptyState =
    !chat.isLoading && chat.messages.length === 0 && !chat.streamingText && !chat.isSending

  return (
    <div className="chat-shell">
      <aside className="chat-sidebar">
        <div className="chat-sidebar-header">
          <div className="chat-sidebar-title">
            <MessageSquare size={18} />
            <span>监控助手</span>
          </div>
          <button
            type="button"
            className="demo-button demo-button-sm chat-new-session-btn"
            disabled={!snapshotId || isCreatingSession || chat.isSending}
            onClick={() => void handleNewSession()}
          >
            {isCreatingSession ? <Loader2 size={14} className="chat-spin" /> : <Plus size={14} />}
            新会话
          </button>
        </div>
        <div className={`chat-session-list${chat.isSending ? ' chat-session-list-locked' : ''}`}>
          {sessions.length === 0 ? (
            <p className="chat-session-empty">暂无会话</p>
          ) : (
            sessions.map((s) => (
              <Link
                key={s.id}
                to="/chat"
                search={{
                  session_id: s.id,
                  snapshot_id: s.snapshot_id,
                  sku: s.sku ?? undefined,
                  warehouse: s.warehouse ?? undefined,
                }}
                className={
                  s.id === sessionId ? 'chat-session-item active' : 'chat-session-item'
                }
                tabIndex={chat.isSending ? -1 : undefined}
                aria-disabled={chat.isSending}
              >
                <div className="chat-session-title">{s.title || `会话 #${s.id}`}</div>
                <div className="chat-session-meta">快照 {s.snapshot_id}</div>
              </Link>
            ))
          )}
        </div>
      </aside>

      <section className="chat-main">
        <header className="chat-main-header">
          <h1 className="chat-main-title">监控助手</h1>
          {snapshotId ? (
            <span className="chat-main-meta">快照 {snapshotId}</span>
          ) : (
            <span className="chat-main-meta">请先在顶栏选择快照</span>
          )}
        </header>

        <div className="chat-messages">
          {chat.isLoading ? <p className="demo-muted text-sm">加载会话…</p> : null}
          {showEmptyState ? (
            <div className="chat-empty-state">
              <p>可询问日报摘要、风险清单或 SKU 分析。</p>
              <p className="chat-empty-hint">例如：「今天有哪些红色预警？」「分析 SKU-001 的断货风险」</p>
            </div>
          ) : null}
          {chat.messages.map((msg) => (
            <div
              key={msg.id}
              className={msg.role === 'user' ? 'chat-message chat-message-user' : 'chat-message'}
            >
              <div className="chat-message-role">{msg.role === 'user' ? '你' : '助手'}</div>
              <div className="chat-message-body">{msg.content}</div>
              {msg.explanation_draft ? (
                <div className="chat-draft-card">
                  <div className="chat-draft-title">解释草稿</div>
                  <p>{msg.explanation_draft.primary_explanation}</p>
                  <p className="text-sm text-[var(--sea-ink-muted)]">
                    建议：{msg.explanation_draft.suggested_action}
                  </p>
                  <button
                    type="button"
                    className="demo-button demo-button-sm"
                    onClick={() => void chat.adoptExplanation(msg.id)}
                  >
                    采纳解释
                  </button>
                </div>
              ) : null}
            </div>
          ))}
          {chat.isSending && !chat.streamingText ? (
            <div className="chat-message chat-message-thinking">
              <div className="chat-message-role">助手</div>
              <div className="chat-thinking">
                <Loader2 size={14} className="chat-spin" />
                助手正在思考…
              </div>
            </div>
          ) : null}
          {chat.streamingText ? (
            <div className="chat-message">
              <div className="chat-message-role">助手</div>
              <div className="chat-message-body">{chat.streamingText}</div>
            </div>
          ) : null}
          {chat.pendingDraft && !chat.messages.some((m) => m.explanation_draft) ? (
            <div className="chat-draft-card">
              <div className="chat-draft-title">解释草稿（待刷新）</div>
              <p>{chat.pendingDraft.primary_explanation}</p>
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>

        {sessionActionError ? (
          <div className="chat-error-bar">
            <div className="demo-alert demo-alert-danger chat-error-alert">
              <span>{sessionActionError}</span>
              <button
                type="button"
                className="chat-error-dismiss"
                aria-label="关闭"
                onClick={() => setSessionActionError(null)}
              >
                <X size={14} />
              </button>
            </div>
          </div>
        ) : null}

        {chat.error ? (
          <div className="chat-error-bar">
            <div className="demo-alert demo-alert-danger chat-error-alert">
              <span>{chat.error}</span>
              <div className="chat-error-actions">
                {retryText ? (
                  <button type="button" className="demo-button demo-button-sm" onClick={handleRetry}>
                    重试
                  </button>
                ) : null}
                <button
                  type="button"
                  className="chat-error-dismiss"
                  aria-label="关闭"
                  onClick={() => {
                    chat.clearError()
                    setRetryText(null)
                  }}
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <form className="chat-composer" onSubmit={handleSubmit}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="询问日报、风险清单或 SKU 分析…"
            disabled={!sessionId || chat.isSending}
          />
          <button type="submit" className="demo-button" disabled={!sessionId || chat.isSending}>
            {chat.isSending ? (
              <>
                <Loader2 size={14} className="chat-spin" />
                思考中…
              </>
            ) : (
              <>
                <Send size={14} />
                发送
              </>
            )}
          </button>
        </form>
      </section>
    </div>
  )
}

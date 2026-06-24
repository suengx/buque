import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, MessageSquare, Plus, Send, X } from 'lucide-react'
import { useSnapshot } from '#/context/SnapshotContext'
import { useExpertChat } from '#/hooks/useExpertChat'
import { expertApi, type AgentPhase } from '#/lib/expert-api'
import { ChatMessageContent } from '#/components/buque/ChatMessageContent'
import { ChatMessageActions } from '#/components/buque/ChatMessageActions'
import { ChatProcessTimeline } from '#/components/buque/ChatProcessTimeline'

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

function sendButtonLabel(phase: AgentPhase): string {
  if (phase === 'connecting') return '连接中…'
  if (phase === 'thinking') return '思考中…'
  if (phase === 'tool_running') return '查询中…'
  if (phase === 'streaming') return '输出中…'
  if (phase === 'saving') return '保存中…'
  return '思考中…'
}

function pickLatestSession(
  list: Awaited<ReturnType<typeof expertApi.listSessions>>,
  snapshotId: number,
) {
  const forSnapshot = list.filter((session) => session.snapshot_id === snapshotId)
  const pool = forSnapshot.length > 0 ? forSnapshot : list
  return pool.sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  )[0]
}

function ChatPage() {
  const navigate = useNavigate()
  const search = Route.useSearch()
  const { selectedSnapshotId, setSelectedSnapshotId } = useSnapshot()
  const sessionId = search.session_id
  const [sessions, setSessions] = useState<Awaited<ReturnType<typeof expertApi.listSessions>>>([])
  const [input, setInput] = useState('')
  const [retryText, setRetryText] = useState<string | null>(null)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [isRestoringSession, setIsRestoringSession] = useState(false)
  const [sessionActionError, setSessionActionError] = useState<string | null>(null)
  const seededRef = useRef(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const snapshotId = search.snapshot_id ?? selectedSnapshotId

  const chat = useExpertChat(sessionId)

  const loadSessions = useCallback(async () => {
    try {
      const list = await expertApi.listSessions()
      setSessions(list)
      return list
    } catch {
      setSessions([])
      return []
    }
  }, [])

  useEffect(() => {
    if (search.snapshot_id) {
      setSelectedSnapshotId(search.snapshot_id)
    }
  }, [search.snapshot_id, setSelectedSnapshotId])

  useEffect(() => {
    void loadSessions()
  }, [loadSessions, sessionId, chat.messages.length])

  useEffect(() => {
    if (sessionId || !snapshotId) return
    let cancelled = false
    setIsRestoringSession(true)
    ;(async () => {
      try {
        const list = await expertApi.listSessions()
        if (cancelled) return
        const latest = pickLatestSession(list, snapshotId)
        if (!latest) return
        void navigate({
          to: '/chat',
          search: {
            session_id: latest.id,
            snapshot_id: snapshotId,
            sku: latest.sku ?? undefined,
            warehouse: latest.warehouse ?? undefined,
          },
          replace: true,
        })
      } catch {
        /* stay empty */
      } finally {
        if (!cancelled) setIsRestoringSession(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [sessionId, snapshotId, navigate])

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
  }, [chat.messages, chat.streamingText, chat.isSending, chat.turnTrace])

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

  const ensureSessionAndSend = async (text: string) => {
    let activeSessionId = sessionId
    if (!activeSessionId) {
      if (!snapshotId) {
        setSessionActionError('请先在顶栏选择快照')
        return
      }
      setIsCreatingSession(true)
      setSessionActionError(null)
      try {
        const created = await expertApi.createSession({
          snapshot_id: snapshotId,
          sku: search.sku,
          warehouse: search.warehouse,
        })
        await loadSessions()
        activeSessionId = created.id
        await navigate({
          to: '/chat',
          search: {
            session_id: created.id,
            snapshot_id: snapshotId,
            sku: search.sku,
            warehouse: search.warehouse,
          },
          replace: true,
        })
      } catch (err) {
        setSessionActionError(err instanceof Error ? err.message : '创建会话失败')
        return
      } finally {
        setIsCreatingSession(false)
      }
    }
    await chat.sendMessage(text, activeSessionId)
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || chat.isSending || isCreatingSession || isRestoringSession) return
    setInput('')
    setRetryText(text)
    chat.clearError()
    void ensureSessionAndSend(text)
  }

  const handleRetry = () => {
    if (!retryText) return
    chat.clearError()
    void ensureSessionAndSend(retryText)
    setRetryText(null)
  }

  const composerDisabled =
    !snapshotId || chat.isSending || isCreatingSession || isRestoringSession

  const showEmptyState =
    !chat.isLoading &&
    !isRestoringSession &&
    Boolean(sessionId) &&
    chat.messages.length === 0 &&
    !chat.streamingText &&
    !chat.isSending

  const messagesClassName =
    'chat-messages' +
    (chat.isLoading || isRestoringSession ? ' chat-messages-loading' : '') +
    (showEmptyState ? ' chat-messages-empty' : '') +
    (chat.messages.length > 0 || chat.isSending || chat.streamingText
      ? ' chat-messages-has-content'
      : '')

  return (
    <div className="chat-page">
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

        <div className={messagesClassName}>
          {chat.isLoading || isRestoringSession ? (
            <div className="chat-loading-state">
              <Loader2 size={16} className="chat-spin" />
              <span>加载会话…</span>
            </div>
          ) : null}
          {showEmptyState ? (
            <div className="chat-empty-state">
              <p>可询问日报摘要、风险清单或 SKU 分析。</p>
              <p className="chat-empty-hint">
                例如：「今天有哪些红色预警？」「断货 top3 是哪些？」「分析 SKU-001 的断货风险」
              </p>
            </div>
          ) : null}
          {!chat.isLoading && !isRestoringSession
            ? chat.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={
                    msg.role === 'user' ? 'chat-message chat-message-user' : 'chat-message'
                  }
                >
                  <span className="sr-only">{msg.role === 'user' ? '你' : '助手'}</span>
                  {msg.role === 'assistant' && msg.process_trace?.length ? (
                    <ChatProcessTimeline
                      steps={msg.process_trace}
                      durationMs={msg.process_duration_ms}
                    />
                  ) : null}
                  {msg.role === 'user' ? (
                    <div className="chat-message-body-wrap">
                      <div className="chat-message-body">{msg.content}</div>
                      <ChatMessageActions content={msg.content} />
                    </div>
                  ) : (
                    <>
                      <ChatMessageContent content={msg.content} />
                      <ChatMessageActions content={msg.content} />
                    </>
                  )}
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
              ))
            : null}
          {chat.isSending || chat.streamingText ? (
            <div className="chat-message">
              <span className="sr-only">助手</span>
              {chat.streamingText ? (
                <div className="chat-message-body">
                  <ChatMessageContent content={chat.streamingText} />
                  {chat.agentPhase === 'streaming' ? (
                    <span className="chat-stream-cursor" aria-hidden="true" />
                  ) : null}
                </div>
              ) : null}
              {chat.isSending ? (
                <ChatProcessTimeline
                  steps={chat.turnTrace}
                  isActive
                  elapsedMs={chat.turnElapsedMs}
                  hasStreamingText={Boolean(chat.streamingText)}
                  onCancel={chat.cancelSend}
                />
              ) : null}
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
            disabled={composerDisabled}
          />
          <button type="submit" className="demo-button" disabled={composerDisabled}>
            {chat.isSending ? (
              <>
                <Loader2 size={14} className="chat-spin" />
                {sendButtonLabel(chat.agentPhase)}
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
    </div>
  )
}

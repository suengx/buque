import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronRight,
  Loader2,
  MessageSquare,
  PanelLeftClose,
  Plus,
  Send,
  Square,
  X,
} from 'lucide-react'
import { useSnapshot } from '#/context/SnapshotContext'
import { useExpertChat } from '#/hooks/useExpertChat'
import { expertApi, type AgentPhase } from '#/lib/expert-api'
import { ChatMessageContent } from '#/components/buque/ChatMessageContent'
import { ChatMessageActions } from '#/components/buque/ChatMessageActions'
import { ChatProcessTimeline } from '#/components/buque/ChatProcessTimeline'
import { ChatLanding, type ChatQuickPrompt } from '#/components/buque/ChatLanding'
import { ContextDock } from '#/components/buque/ContextDock'

const SESSIONS_COLLAPSED_KEY = 'buque.chat.sessionsCollapsed'

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

function readSessionsCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(SESSIONS_COLLAPSED_KEY) === 'true'
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
  const [sessionActionError, setSessionActionError] = useState<string | null>(null)
  const [sessionsCollapsed, setSessionsCollapsed] = useState(readSessionsCollapsed)
  const seededRef = useRef(false)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const pendingSendRef = useRef<{ sessionId: number; text: string } | null>(null)
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null)

  const snapshotId = search.snapshot_id ?? selectedSnapshotId

  const chat = useExpertChat(sessionId)

  const loadSessions = useCallback(async () => {
    if (!snapshotId) {
      setSessions([])
      return []
    }
    try {
      const list = await expertApi.listSessions(snapshotId)
      setSessions(list)
      return list
    } catch {
      setSessions([])
      return []
    }
  }, [snapshotId])

  useEffect(() => {
    if (search.snapshot_id) {
      setSelectedSnapshotId(search.snapshot_id)
      return
    }
    if (selectedSnapshotId && !chat.isSending) {
      void navigate({
        to: '/chat',
        search: {
          snapshot_id: selectedSnapshotId,
          ...(sessionId ? { session_id: sessionId, sku: search.sku, warehouse: search.warehouse } : {}),
        },
        replace: true,
      })
    }
  }, [
    search.snapshot_id,
    search.sku,
    search.warehouse,
    selectedSnapshotId,
    sessionId,
    setSelectedSnapshotId,
    navigate,
    chat.isSending,
  ])

  useEffect(() => {
    void loadSessions()
  }, [loadSessions, sessionId, chat.messages.length])

  useEffect(() => {
    if (!sessionId || !snapshotId || chat.isLoading || chat.isSending) return
    if (!chat.session) return
    if (chat.session.snapshot_id === snapshotId) return
    seededRef.current = false
    void navigate({
      to: '/chat',
      search: { snapshot_id: snapshotId },
      replace: true,
    })
  }, [
    sessionId,
    snapshotId,
    chat.session,
    chat.isLoading,
    chat.isSending,
    navigate,
  ])

  useEffect(() => {
    const pending = pendingSendRef.current
    if (!pending || !sessionId || sessionId !== pending.sessionId) return
    if (chat.isLoading || chat.isSending) return
    pendingSendRef.current = null
    setPendingUserMessage(null)
    void chat.sendMessage(pending.text)
  }, [sessionId, chat.isLoading, chat.isSending, chat.sendMessage])

  useEffect(() => {
    localStorage.setItem(SESSIONS_COLLAPSED_KEY, String(sessionsCollapsed))
  }, [sessionsCollapsed])

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

  const scrollMessagesToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const container = messagesContainerRef.current
    if (!container) return
    container.scrollTo({ top: container.scrollHeight, behavior })
  }, [])

  useEffect(() => {
    scrollMessagesToBottom()
  }, [chat.messages, chat.streamingText, chat.isSending, scrollMessagesToBottom])

  const handleNewSession = () => {
    if (!snapshotId || chat.isSending) return
    setSessionActionError(null)
    chat.clearError()
    seededRef.current = false
    pendingSendRef.current = null
    setPendingUserMessage(null)
    void navigate({
      to: '/chat',
      search: { snapshot_id: snapshotId },
    })
  }

  const ensureSessionAndSend = async (text: string) => {
    if (!sessionId) {
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
        pendingSendRef.current = { sessionId: created.id, text }
        setPendingUserMessage(text)
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
        pendingSendRef.current = null
        setPendingUserMessage(null)
        setSessionActionError(err instanceof Error ? err.message : '创建会话失败')
        return
      } finally {
        setIsCreatingSession(false)
      }
      return
    }
    await chat.sendMessage(text)
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || chat.isSending || isCreatingSession) return
    setInput('')
    setRetryText(text)
    chat.clearError()
    void ensureSessionAndSend(text)
  }

  const handleQuickPrompt = (prompt: ChatQuickPrompt) => {
    if (prompt.kind !== 'send') return
    setRetryText(prompt.text)
    chat.clearError()
    void ensureSessionAndSend(prompt.text)
  }

  const handleRetry = () => {
    if (!retryText) return
    chat.clearError()
    void ensureSessionAndSend(retryText)
    setRetryText(null)
  }

  const handleSnapshotSelect = (id: number) => {
    if (chat.isSending) return
    setSessionActionError(null)
    chat.clearError()
    seededRef.current = false
    pendingSendRef.current = null
    setPendingUserMessage(null)
    void navigate({
      to: '/chat',
      search: { snapshot_id: id },
    })
  }

  const composerInputDisabled = !snapshotId || chat.isSending || isCreatingSession
  const composerSendDisabled = !snapshotId || isCreatingSession
  const showLanding =
    !sessionId && !chat.isSending && !chat.streamingText && !pendingUserMessage && !isCreatingSession
  const showMessageHistory = Boolean(sessionId) && (!chat.isLoading || chat.messages.length > 0)

  const messagesClassName =
    'chat-messages' +
    (showLanding ? ' chat-messages-landing' : '') +
    (chat.isLoading ? ' chat-messages-loading' : '')

  return (
    <div className="chat-page">
      <div
        className="chat-shell"
        data-sessions-collapsed={sessionsCollapsed ? 'true' : undefined}
      >
        {sessionsCollapsed ? (
          <button
            type="button"
            className="chat-sessions-expand-handle"
            aria-label="展开会话列表"
            onClick={() => setSessionsCollapsed(false)}
          >
            <ChevronRight size={14} />
          </button>
        ) : null}
        <aside className="chat-sidebar">
          <div className="chat-sidebar-header">
            <div className="chat-sidebar-title">
              <MessageSquare size={18} />
              <span>监控助手</span>
            </div>
            <div className="chat-sidebar-actions">
              <button
                type="button"
                className="demo-button demo-button-sm chat-new-session-btn"
                disabled={!snapshotId || chat.isSending}
                onClick={handleNewSession}
              >
                <Plus size={14} />
                新会话
              </button>
              <button
                type="button"
                className="chat-sessions-collapse-btn"
                aria-label="折叠会话列表"
                onClick={() => setSessionsCollapsed(true)}
              >
                <PanelLeftClose size={14} />
              </button>
            </div>
          </div>
          <div className={`chat-session-list${chat.isSending ? ' chat-session-list-locked' : ''}`}>
            {!snapshotId ? (
              <p className="chat-session-empty">请先选择快照</p>
            ) : sessions.length === 0 ? (
              <p className="chat-session-empty">该快照下暂无会话</p>
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
                </Link>
              ))
            )}
          </div>
        </aside>

        <section className="chat-main">
          <header className="chat-main-header">
            {sessionId ? <h1 className="chat-main-title">监控助手</h1> : <span />}
            <ContextDock placement="inline" onSnapshotSelect={handleSnapshotSelect} />
          </header>

          <div ref={messagesContainerRef} className={messagesClassName}>
            {showLanding ? (
              <ChatLanding
                input={input}
                onInputChange={setInput}
                onSubmit={handleSubmit}
                onQuickPrompt={handleQuickPrompt}
                disabled={composerInputDisabled}
                isSending={chat.isSending}
                sendLabel={sendButtonLabel(chat.agentPhase)}
              />
            ) : null}
            {chat.isLoading && !showMessageHistory && !pendingUserMessage ? (
              <div className="chat-loading-state">
                <Loader2 size={16} className="chat-spin" />
                <span>加载会话…</span>
              </div>
            ) : null}
            {pendingUserMessage && sessionId ? (
              <div className="chat-message chat-message-user">
                <span className="sr-only">你</span>
                <div className="chat-message-body-wrap">
                  <div className="chat-message-body">{pendingUserMessage}</div>
                </div>
              </div>
            ) : null}
            {showMessageHistory
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

          {!showLanding ? (
            <form className="chat-composer" onSubmit={handleSubmit}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="询问日报、风险清单或 SKU 分析…"
                disabled={composerInputDisabled}
              />
              {chat.isSending ? (
                <button
                  type="button"
                  className="demo-button demo-button-stop"
                  onClick={() => chat.cancelSend()}
                >
                  <Square size={14} />
                  停止
                </button>
              ) : (
                <button type="submit" className="demo-button" disabled={composerSendDisabled}>
                  <Send size={14} />
                  发送
                </button>
              )}
            </form>
          ) : null}
        </section>
      </div>
    </div>
  )
}

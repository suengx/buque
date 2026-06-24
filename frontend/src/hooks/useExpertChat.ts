import { useCallback, useEffect, useRef, useState } from 'react'
import {
  expertApi,
  type AgentPhase,
  type ChatMessage,
  type ChatSession,
  type ExplanationDraft,
  type ProcessStep,
  type StreamToolPayload,
} from '#/lib/expert-api'
import { compressProcessTrace } from '#/lib/process-trace'

const IDLE_PHASE: AgentPhase = 'idle'
const HIDDEN_PHASES = new Set(['started', 'saving'])

function mapStatusPhase(phase: string): AgentPhase {
  if (phase === 'started') return 'connecting'
  if (phase === 'thinking') return 'thinking'
  if (phase === 'tool_running') return 'tool_running'
  if (phase === 'saving') return 'saving'
  return 'thinking'
}

function appendStatusStep(steps: ProcessStep[], phase: string, label: string): ProcessStep[] {
  if (HIDDEN_PHASES.has(phase)) return steps
  const last = steps[steps.length - 1]
  if (last?.kind === 'status' && last.phase === phase) {
    return [...steps.slice(0, -1), { ...last, label, at: new Date().toISOString() }]
  }
  return [...steps, { kind: 'status', phase, label, at: new Date().toISOString() }]
}

function appendToolSteps(steps: ProcessStep[], tools: StreamToolPayload[]): ProcessStep[] {
  const next = [...steps]
  for (const tool of tools) {
    const existing = next.find((step) => step.kind === 'tool' && step.id === tool.id)
    if (existing && existing.kind === 'tool') {
      existing.status = 'running'
      existing.label = tool.label
      existing.name = tool.name
      existing.detail = tool.detail
    } else {
      next.push({
        kind: 'tool',
        id: tool.id,
        name: tool.name,
        label: tool.label,
        detail: tool.detail,
        status: 'running',
        at: new Date().toISOString(),
      })
    }
  }
  return next
}

function markToolResult(
  steps: ProcessStep[],
  toolUseId: string,
  label: string,
  isError: boolean,
): ProcessStep[] {
  return steps.map((step) =>
    step.kind === 'tool' && step.id === toolUseId
      ? { ...step, label, status: isError ? 'error' : 'done' }
      : step,
  )
}

function derivePhase(steps: ProcessStep[], isSending: boolean, hasStreamingText: boolean): AgentPhase {
  if (!isSending) return IDLE_PHASE
  if (hasStreamingText) return 'streaming'
  const lastStatus = [...steps].reverse().find((step) => step.kind === 'status')
  if (lastStatus?.kind === 'status') return mapStatusPhase(lastStatus.phase)
  const hasRunningTool = steps.some(
    (step) => step.kind === 'tool' && step.status === 'running',
  )
  if (hasRunningTool) return 'tool_running'
  return 'connecting'
}

export function useExpertChat(sessionId: number | undefined) {
  const [session, setSession] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingText, setStreamingText] = useState('')
  const [pendingDraft, setPendingDraft] = useState<ExplanationDraft | null>(null)
  const [isLoading, setIsLoading] = useState(() => Boolean(sessionId))
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [turnTrace, setTurnTrace] = useState<ProcessStep[]>([])
  const [turnStartedAt, setTurnStartedAt] = useState<number | null>(null)
  const [turnElapsedMs, setTurnElapsedMs] = useState(0)
  const [stallSeconds, setStallSeconds] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const sendGenerationRef = useRef(0)
  const refreshSeqRef = useRef(0)
  const lastEventAtRef = useRef(0)

  const clearError = useCallback(() => setError(null), [])

  const touchLastEvent = useCallback(() => {
    lastEventAtRef.current = Date.now()
    setStallSeconds(0)
  }, [])

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setSession(null)
      setMessages([])
      return
    }
    const seq = ++refreshSeqRef.current
    setIsLoading(true)
    setError(null)
    try {
      const detail = await expertApi.getSession(sessionId)
      if (seq !== refreshSeqRef.current) return
      setSession(detail)
      setMessages(detail.messages)
    } catch (err) {
      if (seq !== refreshSeqRef.current) return
      setError(err instanceof Error ? err.message : '加载会话失败')
    } finally {
      if (seq === refreshSeqRef.current) {
        setIsLoading(false)
      }
    }
  }, [sessionId])

  useEffect(() => {
    abortRef.current?.abort()
    abortRef.current = null
    sendGenerationRef.current += 1
    refreshSeqRef.current += 1
    setMessages([])
    setSession(null)
    setStreamingText('')
    setPendingDraft(null)
    setError(null)
    setIsSending(false)
    setTurnTrace([])
    setTurnStartedAt(null)
    setTurnElapsedMs(0)
    setStallSeconds(0)
    lastEventAtRef.current = 0
    void refresh()
  }, [sessionId, refresh])

  useEffect(() => {
    if (!isSending) {
      setStallSeconds(0)
      return
    }
    const timer = window.setInterval(() => {
      if (turnStartedAt) {
        setTurnElapsedMs(Date.now() - turnStartedAt)
      }
      if (lastEventAtRef.current <= 0) return
      const elapsed = Math.floor((Date.now() - lastEventAtRef.current) / 1000)
      setStallSeconds(elapsed)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [isSending, turnStartedAt])

  const cancelSend = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const sendMessage = useCallback(
    async (content: string, sessionIdOverride?: number) => {
      const targetSessionId = sessionIdOverride ?? sessionId
      if (!targetSessionId || !content.trim()) return
      const generation = sendGenerationRef.current
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const startedAt = Date.now()
      setIsSending(true)
      setError(null)
      setStreamingText('')
      setPendingDraft(null)
      setTurnTrace([])
      setTurnStartedAt(startedAt)
      setTurnElapsedMs(0)
      setStallSeconds(0)
      touchLastEvent()
      setTurnTrace((steps) => appendStatusStep(steps, 'thinking', '正在思考…'))

      const optimisticId = -Date.now()
      const optimistic: ChatMessage = {
        id: optimisticId,
        role: 'user',
        content,
        explanation_draft: null,
        process_trace: null,
        process_duration_ms: null,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, optimistic])
      let draft: ExplanationDraft | null = null
      try {
        await expertApi.sendMessage(
          targetSessionId,
          content,
          {
            onActivity: () => {
              if (generation !== sendGenerationRef.current) return
              touchLastEvent()
            },
            onStatus: ({ phase, label }) => {
              if (generation !== sendGenerationRef.current) return
              touchLastEvent()
              setTurnTrace((steps) => appendStatusStep(steps, phase, label))
            },
            onProgress: ({ label }) => {
              if (generation !== sendGenerationRef.current) return
              touchLastEvent()
              setTurnTrace((steps) => appendStatusStep(steps, 'tool_running', label))
            },
            onTool: ({ tools }) => {
              if (generation !== sendGenerationRef.current) return
              touchLastEvent()
              setTurnTrace((steps) => appendToolSteps(steps, tools))
            },
            onToolResult: ({ tool_use_id, label, is_error }) => {
              if (generation !== sendGenerationRef.current) return
              touchLastEvent()
              setTurnTrace((steps) => {
                const updated = markToolResult(steps, tool_use_id, label, is_error)
                return appendStatusStep(updated, 'thinking', '正在思考…')
              })
            },
            onDelta: (text) => {
              if (generation !== sendGenerationRef.current) return
              touchLastEvent()
              setStreamingText((prev) => prev + text)
            },
            onDraft: (d) => {
              if (generation !== sendGenerationRef.current) return
              draft = d
              setPendingDraft(d)
            },
          },
          controller.signal,
        )
        if (generation !== sendGenerationRef.current) return
        await refresh()
      } catch (err) {
        if (generation !== sendGenerationRef.current) return
        if (controller.signal.aborted) {
          setMessages((prev) => prev.filter((m) => m.id !== optimisticId))
          return
        }
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId))
        setError(err instanceof Error ? err.message : '发送失败')
      } finally {
        if (generation === sendGenerationRef.current) {
          setStreamingText('')
          setIsSending(false)
          setTurnStartedAt(null)
          setStallSeconds(0)
          lastEventAtRef.current = 0
          if (draft) setPendingDraft(draft)
          if (abortRef.current === controller) {
            abortRef.current = null
          }
        } else if (abortRef.current === controller) {
          abortRef.current = null
        }
      }
    },
    [sessionId, refresh, touchLastEvent],
  )

  const adoptExplanation = useCallback(
    async (messageId: number) => {
      if (!sessionId) return
      setError(null)
      try {
        await expertApi.adoptExplanation(sessionId, messageId)
        await refresh()
      } catch (err) {
        setError(err instanceof Error ? err.message : '采纳失败')
      }
    },
    [sessionId, refresh],
  )

  const agentPhase = derivePhase(turnTrace, isSending, Boolean(streamingText))
  const displayTrace = compressProcessTrace(turnTrace)

  return {
    session,
    messages,
    streamingText,
    pendingDraft,
    isLoading,
    isSending,
    error,
    turnTrace: displayTrace,
    turnElapsedMs,
    agentPhase,
    stallSeconds,
    clearError,
    cancelSend,
    sendMessage,
    adoptExplanation,
    refresh,
  }
}

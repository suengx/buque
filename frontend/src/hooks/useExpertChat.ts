import { useCallback, useEffect, useRef, useState } from 'react'
import {
  expertApi,
  type ChatMessage,
  type ChatSession,
  type ExplanationDraft,
} from '#/lib/expert-api'

export function useExpertChat(sessionId: number | undefined) {
  const [session, setSession] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingText, setStreamingText] = useState('')
  const [pendingDraft, setPendingDraft] = useState<ExplanationDraft | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const sendGenerationRef = useRef(0)

  const clearError = useCallback(() => setError(null), [])

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setSession(null)
      setMessages([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const detail = await expertApi.getSession(sessionId)
      setSession(detail)
      setMessages(detail.messages)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载会话失败')
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    abortRef.current?.abort()
    abortRef.current = null
    sendGenerationRef.current += 1
    setStreamingText('')
    setPendingDraft(null)
    setError(null)
    void refresh()
  }, [sessionId, refresh])

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || !content.trim()) return
      const generation = sendGenerationRef.current
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setIsSending(true)
      setError(null)
      setStreamingText('')
      setPendingDraft(null)
      const optimisticId = -Date.now()
      const optimistic: ChatMessage = {
        id: optimisticId,
        role: 'user',
        content,
        explanation_draft: null,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, optimistic])
      let draft: ExplanationDraft | null = null
      try {
        await expertApi.sendMessage(
          sessionId,
          content,
          {
            onDelta: (text) => {
              if (generation !== sendGenerationRef.current) return
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
        if (controller.signal.aborted || generation !== sendGenerationRef.current) return
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId))
        setError(err instanceof Error ? err.message : '发送失败')
      } finally {
        if (generation !== sendGenerationRef.current) return
        setStreamingText('')
        setIsSending(false)
        if (draft) setPendingDraft(draft)
        if (abortRef.current === controller) {
          abortRef.current = null
        }
      }
    },
    [sessionId, refresh],
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

  return {
    session,
    messages,
    streamingText,
    pendingDraft,
    isLoading,
    isSending,
    error,
    clearError,
    sendMessage,
    adoptExplanation,
    refresh,
  }
}

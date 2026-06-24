import { apiRequest } from '#/lib/api'

export type ExplanationDraft = {
  sku?: string | null
  warehouse?: string | null
  primary_explanation: string
  secondary_explanation?: string | null
  tertiary_explanation?: string | null
  explanation_tags?: string[]
  key_evidence?: string[]
  suggested_action: string
  responsible_role?: string | null
  action_deadline?: string | null
  require_human_confirm?: boolean
  confidence_note?: string | null
}

export type ChatMessage = {
  id: number
  role: string
  content: string
  explanation_draft: ExplanationDraft | null
  created_at: string
}

export type ChatSession = {
  id: number
  snapshot_id: number
  sku?: string | null
  warehouse?: string | null
  title?: string | null
  created_at: string
  updated_at: string
}

export type ChatSessionDetail = ChatSession & {
  messages: ChatMessage[]
}

export type ExpertStreamHandlers = {
  onDelta?: (text: string) => void
  onDraft?: (draft: ExplanationDraft) => void
  onDone?: (messageId: number) => void
  onError?: (message: string) => void
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = 'message'
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!data) return null
  return { event, data }
}

function parseHttpError(text: string, status: number): string {
  try {
    const payload = JSON.parse(text) as { detail?: string | { msg?: string }[] }
    if (typeof payload.detail === 'string') return payload.detail
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
      return payload.detail[0].msg
    }
  } catch {
    /* use fallback */
  }
  return text.trim() || `请求失败（HTTP ${status}）`
}

export const expertApi = {
  createSession: (body: {
    snapshot_id: number
    sku?: string
    warehouse?: string
    seed?: string
  }) =>
    apiRequest<ChatSession>('/expert/sessions', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listSessions: () => apiRequest<ChatSession[]>('/expert/sessions'),
  getSession: (sessionId: number) =>
    apiRequest<ChatSessionDetail>(`/expert/sessions/${sessionId}`),
  adoptExplanation: (sessionId: number, messageId: number) =>
    apiRequest<{ snapshot_id: number; sku: string; primary_explanation: string }>(
      `/expert/sessions/${sessionId}/adopt-explanation`,
      {
        method: 'POST',
        body: JSON.stringify({ message_id: messageId }),
      },
    ),
  async sendMessage(
    sessionId: number,
    content: string,
    handlers: ExpertStreamHandlers = {},
    signal?: AbortSignal,
  ): Promise<void> {
    const token = localStorage.getItem('buque_token')
    const base = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
    const res = await fetch(`${base}/expert/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
      signal,
    })
    if (!res.ok) {
      const text = await res.text()
      const message = parseHttpError(text, res.status)
      handlers.onError?.(message)
      throw new Error(message)
    }
    if (!res.body) {
      const message = '无流式响应'
      handlers.onError?.(message)
      throw new Error(message)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let sawDone = false
    let streamError: string | null = null
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const parsed = parseSseBlock(part)
          if (!parsed) continue
          try {
            const payload = JSON.parse(parsed.data) as Record<string, unknown>
            if (parsed.event === 'delta' && typeof payload.text === 'string') {
              handlers.onDelta?.(payload.text)
            } else if (parsed.event === 'draft') {
              handlers.onDraft?.(payload.draft as ExplanationDraft)
            } else if (parsed.event === 'done' && typeof payload.message_id === 'number') {
              sawDone = true
              handlers.onDone?.(payload.message_id)
            } else if (parsed.event === 'error' && typeof payload.message === 'string') {
              streamError = payload.message
              handlers.onError?.(payload.message)
            }
          } catch {
            /* ignore malformed chunk */
          }
        }
      }
    } catch (err) {
      if (signal?.aborted) return
      const message = err instanceof Error ? err.message : '助手连接中断，请重试'
      handlers.onError?.(message)
      throw new Error(message)
    }
    if (streamError) {
      throw new Error(streamError)
    }
    if (!sawDone) {
      const message = '助手连接中断，请重试'
      handlers.onError?.(message)
      throw new Error(message)
    }
  },
}

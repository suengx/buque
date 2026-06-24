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

export type ProcessStep =
  | { kind: 'status'; phase: string; label: string; at: string }
  | {
      kind: 'tool'
      id: string
      name: string
      label: string
      status: 'running' | 'done' | 'error'
      at: string
      detail?: string
    }

export type ChatMessage = {
  id: number
  role: string
  content: string
  explanation_draft: ExplanationDraft | null
  process_trace: ProcessStep[] | null
  process_duration_ms: number | null
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

export type AgentPhase =
  | 'idle'
  | 'connecting'
  | 'thinking'
  | 'streaming'
  | 'tool_running'
  | 'saving'

export type ToolActivity = {
  id: string
  name: string
  label: string
  status: 'running' | 'done' | 'error'
}

export type StreamToolPayload = {
  id: string
  name: string
  label: string
  detail?: string
}

export type ExpertStreamHandlers = {
  onDelta?: (text: string) => void
  onDraft?: (draft: ExplanationDraft) => void
  onDone?: (messageId: number) => void
  onError?: (message: string) => void
  onStatus?: (payload: { phase: string; label: string }) => void
  onTool?: (payload: { tools: StreamToolPayload[]; status: string }) => void
  onToolResult?: (payload: {
    tool_use_id: string
    name: string
    label: string
    is_error: boolean
  }) => void
  onProgress?: (payload: {
    description: string
    last_tool_name: string | null
    label: string
  }) => void
  onActivity?: () => void
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

function dispatchStreamEvent(
  event: string,
  payload: Record<string, unknown>,
  handlers: ExpertStreamHandlers,
): void {
  handlers.onActivity?.()
  if (event === 'delta' && typeof payload.text === 'string') {
    handlers.onDelta?.(payload.text)
  } else if (event === 'draft') {
    handlers.onDraft?.(payload.draft as ExplanationDraft)
  } else if (event === 'done' && typeof payload.message_id === 'number') {
    handlers.onDone?.(payload.message_id)
  } else if (event === 'error' && typeof payload.message === 'string') {
    handlers.onError?.(payload.message)
  } else if (event === 'status' && typeof payload.phase === 'string') {
    handlers.onStatus?.({
      phase: payload.phase,
      label: typeof payload.label === 'string' ? payload.label : '正在处理…',
    })
  } else if (event === 'tool' && Array.isArray(payload.tools)) {
    handlers.onTool?.({
      tools: payload.tools as StreamToolPayload[],
      status: typeof payload.status === 'string' ? payload.status : 'started',
    })
  } else if (event === 'tool_result' && typeof payload.tool_use_id === 'string') {
    handlers.onToolResult?.({
      tool_use_id: payload.tool_use_id,
      name: typeof payload.name === 'string' ? payload.name : payload.tool_use_id,
      label: typeof payload.label === 'string' ? payload.label : '工具',
      is_error: Boolean(payload.is_error),
    })
  } else if (event === 'progress') {
    handlers.onProgress?.({
      description: typeof payload.description === 'string' ? payload.description : '',
      last_tool_name:
        typeof payload.last_tool_name === 'string' ? payload.last_tool_name : null,
      label: typeof payload.label === 'string' ? payload.label : '正在处理…',
    })
  }
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
            if (parsed.event === 'error' && typeof payload.message === 'string') {
              streamError = payload.message
            }
            if (parsed.event === 'done' && typeof payload.message_id === 'number') {
              sawDone = true
            }
            dispatchStreamEvent(parsed.event, payload, handlers)
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

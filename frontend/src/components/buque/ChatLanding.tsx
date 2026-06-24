import { useRef } from 'react'
import { Loader2, Send } from 'lucide-react'

export type ChatQuickPrompt =
  | { kind: 'send'; label: string; text: string }
  | { kind: 'prefill'; label: string; text: string }

export const CHAT_QUICK_PROMPTS: ChatQuickPrompt[] = [
  { kind: 'send', label: '今天有哪些红色预警？', text: '今天有哪些红色预警？' },
  { kind: 'send', label: '断货 top3 是哪些？', text: '断货 top3 是哪些？' },
  { kind: 'send', label: '今天库存整体情况如何？', text: '今天库存整体情况如何？' },
  { kind: 'prefill', label: '分析 SKU 断货风险', text: '分析 SKU- 的断货风险' },
]

type ChatLandingProps = {
  input: string
  onInputChange: (value: string) => void
  onSubmit: (event: React.FormEvent) => void
  onQuickPrompt: (prompt: ChatQuickPrompt) => void
  disabled: boolean
  isSending: boolean
  sendLabel: string
}

export function ChatLanding({
  input,
  onInputChange,
  onSubmit,
  onQuickPrompt,
  disabled,
  isSending,
  sendLabel,
}: ChatLandingProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleQuickPrompt = (prompt: ChatQuickPrompt) => {
    if (prompt.kind === 'prefill') {
      onInputChange(prompt.text)
      inputRef.current?.focus()
      return
    }
    onQuickPrompt(prompt)
  }

  return (
    <div className="chat-landing">
      <h2 className="chat-landing-title">今天想了解什么？</h2>
      <form className="chat-landing-composer" onSubmit={onSubmit}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="询问日报、风险清单或 SKU 分析…"
          disabled={disabled}
        />
        <button type="submit" className="demo-button" disabled={disabled}>
          {isSending ? (
            <>
              <Loader2 size={14} className="chat-spin" />
              {sendLabel}
            </>
          ) : (
            <>
              <Send size={14} />
              发送
            </>
          )}
        </button>
      </form>
      <div className="chat-landing-prompts">
        {CHAT_QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt.label}
            type="button"
            className="chat-landing-prompt-chip"
            disabled={disabled}
            onClick={() => handleQuickPrompt(prompt)}
          >
            {prompt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

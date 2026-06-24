import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

type ChatMessageActionsProps = {
  content: string
}

export function ChatMessageActions({ content }: ChatMessageActionsProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="chat-message-actions">
      <button
        type="button"
        className="chat-message-action-btn"
        aria-label={copied ? '已复制' : '复制'}
        onClick={() => void handleCopy()}
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
    </div>
  )
}

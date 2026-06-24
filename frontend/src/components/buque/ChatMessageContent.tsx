import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type ChatMessageContentProps = {
  content: string
}

export function ChatMessageContent({ content }: ChatMessageContentProps) {
  return (
    <div className="chat-message-prose prose prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}

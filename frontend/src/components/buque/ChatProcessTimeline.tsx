import { useEffect, useRef, useState } from 'react'
import { ChevronRight, Loader2 } from 'lucide-react'
import type { ProcessStep } from '#/lib/expert-api'
import {
  formatDurationMs,
  liveActivityLabel,
  stepDisplayText,
} from '#/lib/process-trace'

type ChatProcessTimelineProps = {
  steps: ProcessStep[]
  durationMs?: number | null
  isActive?: boolean
  elapsedMs?: number
  hasStreamingText?: boolean
  onCancel?: () => void
}

export function ChatProcessTimeline({
  steps,
  durationMs,
  isActive = false,
  elapsedMs = 0,
  hasStreamingText = false,
  onCancel,
}: ChatProcessTimelineProps) {
  const [expanded, setExpanded] = useState(false)
  const stepsRef = useRef<HTMLOListElement>(null)

  useEffect(() => {
    if (!expanded || !isActive || !stepsRef.current) return
    stepsRef.current.scrollTop = stepsRef.current.scrollHeight
  }, [steps, expanded, isActive])

  if (steps.length === 0 && !isActive) return null

  const duration = durationMs ?? (isActive ? elapsedMs : 0)
  const showDuration = duration > 0
  const liveLabel = liveActivityLabel(steps)

  if (isActive && !hasStreamingText) {
    return (
      <div className="chat-process-inline chat-process-inline-active">
        <div className="chat-process-live">
          <Loader2 size={12} className="chat-spin" />
          <span>{liveLabel}</span>
          {showDuration ? (
            <span className="chat-process-duration">{formatDurationMs(duration)}</span>
          ) : null}
        </div>
        {onCancel ? (
          <button type="button" className="chat-process-cancel-link" onClick={onCancel}>
            取消
          </button>
        ) : null}
      </div>
    )
  }

  if (isActive && hasStreamingText) {
    return (
      <div className="chat-process-inline chat-process-inline-streaming">
        <div className="chat-process-live">
          <Loader2 size={12} className="chat-spin" />
          <span>{liveLabel}</span>
          {showDuration ? (
            <span className="chat-process-duration">{formatDurationMs(duration)}</span>
          ) : null}
        </div>
        {onCancel ? (
          <button type="button" className="chat-process-cancel-link" onClick={onCancel}>
            取消
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <div className="chat-process-inline">
      <button
        type="button"
        className="chat-process-summary-btn"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <ChevronRight
          size={12}
          className={expanded ? 'chat-process-chevron-expanded' : undefined}
        />
        {showDuration ? (
          <span>已处理 {formatDurationMs(duration)}</span>
        ) : (
          <span>处理过程</span>
        )}
      </button>
      {expanded ? (
        <ol ref={stepsRef} className="chat-process-steps">
          {steps.map((step, index) => (
            <li
              key={`${step.kind}-${step.kind === 'tool' ? step.id : step.phase}-${index}`}
              className="chat-process-step"
            >
              <span className="chat-process-step-text">{stepDisplayText(step)}</span>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}

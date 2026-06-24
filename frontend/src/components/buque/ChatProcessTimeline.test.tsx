import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ChatProcessTimeline } from '#/components/buque/ChatProcessTimeline'
import type { ProcessStep } from '#/lib/expert-api'

const steps: ProcessStep[] = [
  { kind: 'status', phase: 'thinking', label: '正在思考…', at: '2026-06-23T10:00:00Z' },
  {
    kind: 'tool',
    id: 't1',
    name: 'list_alerts',
    label: '查询风险清单',
    detail: 'level=RED, page_size=3',
    status: 'done',
    at: '2026-06-23T10:00:01Z',
  },
]

afterEach(() => {
  cleanup()
})

describe('ChatProcessTimeline', () => {
  it('shows completed duration summary collapsed', () => {
    render(<ChatProcessTimeline steps={steps} durationMs={12000} />)
    expect(screen.getByText('已处理 12s')).toBeTruthy()
    expect(screen.queryByText(/level=RED/)).toBeNull()
  })

  it('expands to show tool detail', () => {
    render(<ChatProcessTimeline steps={steps} durationMs={12000} />)
    fireEvent.click(screen.getByRole('button', { name: /已处理 12s/ }))
    expect(screen.getByText('查询风险清单 · level=RED, page_size=3')).toBeTruthy()
  })

  it('shows active muted line while sending', () => {
    const activeSteps: ProcessStep[] = [
      {
        kind: 'tool',
        id: 't2',
        name: 'list_alerts',
        label: '查询风险清单',
        detail: 'level=RED',
        status: 'running',
        at: '2026-06-23T10:00:02Z',
      },
    ]
    render(
      <ChatProcessTimeline
        steps={activeSteps}
        isActive
        elapsedMs={5000}
        onCancel={() => {}}
      />,
    )
    expect(screen.getByText(/查询风险清单/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '取消' })).toBeTruthy()
  })
})

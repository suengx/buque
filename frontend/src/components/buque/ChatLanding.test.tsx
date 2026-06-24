import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatLanding } from '#/components/buque/ChatLanding'

afterEach(() => {
  cleanup()
})

describe('ChatLanding', () => {
  it('submits composer form', () => {
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault())
    render(
      <ChatLanding
        input=""
        onInputChange={() => {}}
        onSubmit={onSubmit}
        onQuickPrompt={() => {}}
        disabled={false}
        isSending={false}
        sendLabel="思考中…"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '发送' }))
    expect(onSubmit).toHaveBeenCalled()
  })

  it('send prompt triggers quick prompt handler', () => {
    const onQuickPrompt = vi.fn()
    render(
      <ChatLanding
        input=""
        onInputChange={() => {}}
        onSubmit={() => {}}
        onQuickPrompt={onQuickPrompt}
        disabled={false}
        isSending={false}
        sendLabel="思考中…"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '今天有哪些红色预警？' }))
    expect(onQuickPrompt).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'send', text: '今天有哪些红色预警？' }),
    )
  })

  it('prefill prompt updates input', () => {
    const onInputChange = vi.fn()
    render(
      <ChatLanding
        input=""
        onInputChange={onInputChange}
        onSubmit={() => {}}
        onQuickPrompt={() => {}}
        disabled={false}
        isSending={false}
        sendLabel="思考中…"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '分析 SKU 断货风险' }))
    expect(onInputChange).toHaveBeenCalledWith('分析 SKU- 的断货风险')
  })
})

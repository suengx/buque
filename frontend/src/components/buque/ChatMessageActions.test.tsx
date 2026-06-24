import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatMessageActions } from '#/components/buque/ChatMessageActions'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ChatMessageActions', () => {
  it('copies message content to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    render(<ChatMessageActions content="测试消息" />)
    fireEvent.click(screen.getByRole('button', { name: '复制' }))

    expect(writeText).toHaveBeenCalledWith('测试消息')
  })
})

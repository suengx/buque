import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChatMessageContent } from '#/components/buque/ChatMessageContent'

describe('ChatMessageContent', () => {
  it('renders markdown tables', () => {
    const markdown = `| SKU | 等级 |
| --- | --- |
| A-1 | RED |`
    render(<ChatMessageContent content={markdown} />)
    expect(screen.getByRole('table')).toBeTruthy()
    expect(screen.getByText('SKU')).toBeTruthy()
    expect(screen.getByText('A-1')).toBeTruthy()
  })
})

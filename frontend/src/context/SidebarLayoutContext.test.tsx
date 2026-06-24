import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { SidebarLayoutProvider, useSidebarLayout } from '#/context/SidebarLayoutContext'

function TestConsumer() {
  const { collapsed, toggleCollapsed } = useSidebarLayout()
  return (
    <div>
      <span data-testid="collapsed">{String(collapsed)}</span>
      <button type="button" onClick={toggleCollapsed}>
        toggle
      </button>
    </div>
  )
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  delete document.documentElement.dataset.sidebarCollapsed
})

describe('SidebarLayoutContext', () => {
  it('defaults to expanded', () => {
    render(
      <SidebarLayoutProvider>
        <TestConsumer />
      </SidebarLayoutProvider>,
    )
    expect(screen.getByTestId('collapsed').textContent).toBe('false')
  })

  it('restores collapsed from localStorage', () => {
    localStorage.setItem('buque.sidebar.collapsed', 'true')
    render(
      <SidebarLayoutProvider>
        <TestConsumer />
      </SidebarLayoutProvider>,
    )
    expect(screen.getByTestId('collapsed').textContent).toBe('true')
  })

  it('toggles and persists collapsed state', () => {
    render(
      <SidebarLayoutProvider>
        <TestConsumer />
      </SidebarLayoutProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(screen.getByTestId('collapsed').textContent).toBe('true')
    expect(localStorage.getItem('buque.sidebar.collapsed')).toBe('true')
    expect(document.documentElement.dataset.sidebarCollapsed).toBe('true')
  })
})

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Markdown } from '../components/chat/Markdown'

describe('Markdown', () => {
  it('renders headings', () => {
    render(<Markdown># Hello</Markdown>)
    const h = screen.getByRole('heading', { level: 1 })
    expect(h).toHaveTextContent('Hello')
  })

  it('renders bold text', () => {
    render(<Markdown>{'This is **bold** text'}</Markdown>)
    expect(screen.getByText('bold')).toBeInTheDocument()
  })

  it('opens links in a new tab', () => {
    render(<Markdown>{'[click](https://example.com)'}</Markdown>)
    const link = screen.getByRole('link', { name: 'click' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

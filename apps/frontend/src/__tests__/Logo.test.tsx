import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Logo } from '../components/Logo'

describe('Logo', () => {
  it('renders an svg with the accessible label', () => {
    const { container } = render(<Logo className="h-8 w-8" />)
    const svg = container.querySelector('svg')
    expect(svg).toBeTruthy()
    expect(svg?.getAttribute('aria-label')).toBe('AgentDesk')
  })
})

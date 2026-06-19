import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Memory } from '../views/Memory'
import { memoriesApi } from '../api/memories'

vi.mock('../api/memories', () => ({
  memoriesApi: {
    list: vi.fn(),
    search: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockMemory = {
  id: 'mem_001',
  scope: 'global' as const,
  scope_id: null,
  type: 'preference' as const,
  title: 'Prefere Python',
  content: 'Usa Python para automacoes',
  tags: ['python'],
  confidence: 0.9,
  importance: 0.8,
  source: {},
  created_at: '2026-06-18T00:00:00',
  updated_at: '2026-06-18T00:00:00',
  last_used_at: null,
  usage_count: 0,
  deleted_at: null,
  embedding_status: 'done' as const,
}

describe('Memory view', () => {
  beforeEach(() => {
    vi.mocked(memoriesApi.list).mockResolvedValue([mockMemory])
    vi.mocked(memoriesApi.search).mockResolvedValue({ results: [] })
    vi.mocked(memoriesApi.create).mockResolvedValue(mockMemory)
    vi.mocked(memoriesApi.delete).mockResolvedValue({ status: 'deleted' })
  })

  it('renders memory list', async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText('Prefere Python')).toBeInTheDocument()
    })
  })

  it('calls list API on mount', async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>)

    await waitFor(() => {
      expect(memoriesApi.list).toHaveBeenCalled()
    })
  })

  it('calls search API when search button is clicked', async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>)
    await waitFor(() => screen.getByText('Prefere Python'))

    fireEvent.change(screen.getByPlaceholderText('Search memories...'), {
      target: { value: 'python' },
    })
    fireEvent.click(screen.getByText('Search'))

    await waitFor(() => {
      expect(memoriesApi.search).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'python' }),
      )
    })
  })
})

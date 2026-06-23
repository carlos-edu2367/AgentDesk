import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Skills } from '../views/Skills'
import { skillsApi } from '../api/skills'

vi.mock('../api/skills', () => ({
  skillsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'skill_report_writer',
        name: 'Report Writer',
        version: '0.1.0',
        description: 'Writes reports',
        tags: ['writing'],
        prompt: 'Use summary and findings.',
        examples: [],
      },
    ]),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({ status: 'deleted' }),
    importSkill: vi.fn().mockResolvedValue({}),
    exportSkill: vi.fn().mockResolvedValue({ id: 'skill_report_writer' }),
  },
}))

describe('Skills page', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders skills and prompt preview', async () => {
    render(<MemoryRouter><Skills /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Report Writer')).toBeInTheDocument()
      expect(screen.getByText('Use summary and findings.')).toBeInTheDocument()
    })
    expect(screen.getByPlaceholderText('Search skills by name, tag, purpose, or ID')).toBeInTheDocument()
    expect(screen.queryByText('Import / Export JSON')).not.toBeInTheDocument()
  })

  it('creates a skill through the form', async () => {
    render(<MemoryRouter><Skills /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Report Writer')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'New Skill' }))
    expect(screen.getByPlaceholderText('Technical Code Reviewer')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Write concrete instructions the agent should follow.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Name'), 'Reviewer')
    await userEvent.type(screen.getByLabelText('ID'), 'skill_reviewer')
    await userEvent.type(screen.getByLabelText('Version'), '0.1.0')
    await userEvent.type(screen.getByLabelText('Description'), 'Reviews answers')
    await userEvent.type(screen.getByLabelText('Prompt'), 'Review for risks.')
    await userEvent.click(screen.getByRole('button', { name: 'Create Skill' }))

    await waitFor(() => {
      expect(skillsApi.create).toHaveBeenCalledWith(expect.objectContaining({
        id: 'skill_reviewer',
        name: 'Reviewer',
        prompt: 'Review for risks.',
      }))
    })
  })

  it('keeps JSON import collapsed until requested', async () => {
    render(<MemoryRouter><Skills /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Report Writer')).toBeInTheDocument())

    expect(screen.queryByPlaceholderText('Paste exported skill JSON here')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Import JSON' }))

    expect(screen.getByPlaceholderText('Paste exported skill JSON here')).toBeInTheDocument()
  })
})

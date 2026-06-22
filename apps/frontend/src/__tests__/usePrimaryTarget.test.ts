import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePrimaryTarget } from '../hooks/usePrimaryTarget'

describe('usePrimaryTarget', () => {
  beforeEach(() => localStorage.clear())

  it('starts null when nothing stored', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    expect(result.current.primary).toBeNull()
  })

  it('sets and reads a primary target', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    act(() => result.current.setPrimary({ type: 'agent', id: 'a1' }))
    expect(result.current.primary).toEqual({ type: 'agent', id: 'a1' })
    expect(result.current.isPrimary('agent', 'a1')).toBe(true)
    expect(result.current.isPrimary('team', 'a1')).toBe(false)
  })

  it('replacing the primary keeps only one', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    act(() => result.current.setPrimary({ type: 'agent', id: 'a1' }))
    act(() => result.current.setPrimary({ type: 'team', id: 't1' }))
    expect(result.current.primary).toEqual({ type: 'team', id: 't1' })
  })

  it('clears the primary', () => {
    const { result } = renderHook(() => usePrimaryTarget())
    act(() => result.current.setPrimary({ type: 'agent', id: 'a1' }))
    act(() => result.current.clearPrimary())
    expect(result.current.primary).toBeNull()
  })

  it('ignores malformed stored values', () => {
    localStorage.setItem('agentdesk.primaryTarget', '{not json')
    const { result } = renderHook(() => usePrimaryTarget())
    expect(result.current.primary).toBeNull()
  })

  it('syncs across two hook instances via custom event', () => {
    const a = renderHook(() => usePrimaryTarget())
    const b = renderHook(() => usePrimaryTarget())
    act(() => a.result.current.setPrimary({ type: 'agent', id: 'a9' }))
    expect(b.result.current.primary).toEqual({ type: 'agent', id: 'a9' })
  })
})

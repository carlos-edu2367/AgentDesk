import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useExecutionEvents } from '../hooks/useExecutionEvents'

class MockEventSource {
  url: string
  onopen: (() => void) | null = null
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  private _closed = false

  constructor(url: string) {
    this.url = url
  }

  close() {
    this._closed = true
  }

  get closed() {
    return this._closed
  }

  // Test helper: simulate receiving a message
  dispatchMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
    }
  }

  dispatchOpen() {
    if (this.onopen) this.onopen()
  }

  dispatchError() {
    if (this.onerror) this.onerror()
  }
}

let mockESInstance: MockEventSource | null = null

beforeEach(() => {
  mockESInstance = null
  vi.stubGlobal('EventSource', class extends MockEventSource {
    constructor(url: string) {
      super(url)
      mockESInstance = this
    }
  })
})

describe('useExecutionEvents', () => {
  it('starts with empty events', () => {
    const { result } = renderHook(() => useExecutionEvents('exec_1'))
    expect(result.current.events).toEqual([])
    expect(result.current.connectionStatus).toBe('connecting')
  })

  it('adds events as they arrive', async () => {
    const { result } = renderHook(() => useExecutionEvents('exec_1'))

    await act(async () => {
      mockESInstance?.dispatchMessage({
        id: 'ev_1',
        execution_id: 'exec_1',
        type: 'execution_started',
        source: 'orchestrator',
        source_id: 'engine',
        content: {},
        created_at: new Date().toISOString(),
      })
    })

    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0].type).toBe('execution_started')
  })

  it('closes connection on sse_close_connection message', async () => {
    const { result } = renderHook(() => useExecutionEvents('exec_1'))

    await act(async () => {
      mockESInstance?.dispatchMessage({ type: 'sse_close_connection' })
    })

    expect(result.current.connectionStatus).toBe('closed')
    expect(mockESInstance?.closed).toBe(true)
  })

  it('does nothing when executionId is null', () => {
    const { result } = renderHook(() => useExecutionEvents(null))
    expect(result.current.events).toEqual([])
    expect(result.current.connectionStatus).toBe('closed')
  })

  it('resets events when executionId changes', async () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useExecutionEvents(id),
      { initialProps: { id: 'exec_1' } },
    )

    await act(async () => {
      mockESInstance?.dispatchMessage({
        id: 'ev_1', execution_id: 'exec_1', type: 'agent_started',
        source: 's', source_id: 's', content: {}, created_at: new Date().toISOString(),
      })
    })

    expect(result.current.events).toHaveLength(1)

    await act(async () => {
      rerender({ id: 'exec_2' })
    })

    expect(result.current.events).toHaveLength(0)
  })

  it('reconnects when reconnectKey changes for the same executionId', async () => {
    const instances: MockEventSource[] = []
    vi.stubGlobal('EventSource', class extends MockEventSource {
      constructor(url: string) {
        super(url)
        instances.push(this)
        mockESInstance = this
      }
    })

    const { rerender } = renderHook(
      ({ reconnectKey }: { reconnectKey: number }) => useExecutionEvents('exec_1', reconnectKey),
      { initialProps: { reconnectKey: 0 } },
    )

    expect(instances).toHaveLength(1)

    await act(async () => {
      rerender({ reconnectKey: 1 })
    })

    expect(instances).toHaveLength(2)
    expect(instances[0].closed).toBe(true)
    expect(instances[1].url).toContain('/api/executions/exec_1/events')
  })
})

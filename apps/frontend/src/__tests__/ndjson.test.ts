import { describe, it, expect } from 'vitest'
import { readNdjson } from '../lib/ndjson'

function streamFrom(chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const enc = new TextEncoder()
      chunks.forEach(c => controller.enqueue(enc.encode(c)))
      controller.close()
    },
  })
  return new Response(body)
}

describe('readNdjson', () => {
  it('parses objects split across chunks', async () => {
    const res = streamFrom(['{"a":1}\n{"a":', '2}\n'])
    const out: unknown[] = []
    for await (const ev of readNdjson(res)) out.push(ev)
    expect(out).toEqual([{ a: 1 }, { a: 2 }])
  })

  it('flushes a trailing line without newline', async () => {
    const res = streamFrom(['{"x":true}'])
    const out: unknown[] = []
    for await (const ev of readNdjson(res)) out.push(ev)
    expect(out).toEqual([{ x: true }])
  })
})

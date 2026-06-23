export async function* readNdjson<T = unknown>(res: Response): AsyncGenerator<T> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) if (line.trim()) yield JSON.parse(line) as T
  }
  if (buf.trim()) yield JSON.parse(buf) as T
}

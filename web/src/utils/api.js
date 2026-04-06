/**
 * utils/api.js
 * 基础 HTTP 客户端，统一处理 base URL 和错误。
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`[${res.status}] ${text}`)
  }
  return res.json()
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  delete: (path) => request('DELETE', path),
}

/** SSE 流式请求，cb(chunk) 每次收到数据回调 */
export async function streamPost(path, body, onChunk, onDone) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value)
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'done') { onDone?.(); return }
          onChunk(data)
        } catch (_) {}
      }
    }
  }
  onDone?.()
}

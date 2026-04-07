/**
 * utils/api.js
 * 基础 HTTP 客户端 + WebSocket 工具函数。
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

/**
 * WebSocket 流式执行。
 * 连接成功后立即发送 {user_message}，逐条接收 dict 事件。
 * 收到 done 或 error 后自动关闭连接。
 *
 * @param {string} path       - WebSocket 路径，如 /ws/workspaces/xxx/run
 * @param {string} userMessage
 * @param {Function} onChunk  - 每条非 done 事件回调
 * @param {Function} onDone   - 收到 done 或连接关闭时回调
 * @param {Function} onError  - 收到 error 事件或连接异常时回调
 * @returns {WebSocket}       - 返回 ws 实例，外部可调用 ws.close() 中止
 */
export function wsRun(path, payload, onChunk, onDone, onError) {
  // http(s):// → ws(s)://；无协议前缀时直接拼
  const wsBase = BASE.replace(/^http/, 'ws')
  const ws = new WebSocket(`${wsBase}${path}`)

  ws.onopen = () => {
    ws.send(JSON.stringify(payload))
  }

  ws.onmessage = (e) => {
    let data
    try {
      data = JSON.parse(e.data)
    } catch (_) {
      return
    }
    if (data.type === 'done') {
      onDone?.()
      ws.close()
      return
    }
    if (data.type === 'error') {
      onError?.(new Error(data.message ?? 'WebSocket error'))
      ws.close()
      return
    }
    onChunk?.(data)
  }

  ws.onerror = () => {
    onError?.(new Error('WebSocket 连接异常'))
  }

  ws.onclose = (e) => {
    // 非正常关闭（1000 = normal）且未被 onmessage 触发 done
    if (e.code !== 1000) {
      onDone?.()
    }
  }

  return ws
}

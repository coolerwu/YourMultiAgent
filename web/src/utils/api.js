/**
 * utils/api.js
 * 基础 HTTP 客户端 + WebSocket 工具函数。
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const AUTH_TOKEN_KEY = 'yourmultiagent-auth-token'
const AUTH_TOKEN_CHANGED_EVENT = 'yourmultiagent-auth-token-changed'

export function getAuthToken() {
  return window.localStorage.getItem(AUTH_TOKEN_KEY) || ''
}

export function setAuthToken(token) {
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_KEY, token)
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_KEY)
  }
  window.dispatchEvent(new CustomEvent(AUTH_TOKEN_CHANGED_EVENT, { detail: { token: token || '' } }))
}

async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getAuthToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    if (res.status === 401) {
      setAuthToken('')
    }
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

export const authApi = {
  status: () => api.get('/api/auth/status'),
  login: (data) => api.post('/api/auth/login', data),
  logout: () => setAuthToken(''),
}

function resolveWebSocketUrl(path) {
  if (/^wss?:\/\//.test(path)) {
    return path
  }

  if (BASE) {
    const normalizedBase = BASE.replace(/^http/, 'ws')
    return `${normalizedBase}${path}`
  }

  if (typeof window !== 'undefined' && window.location?.origin) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${path}`
  }

  return path
}

/**
 * WebSocket 流式执行。
 * 连接成功后立即发送 payload，逐条接收 dict 事件。
 * 收到 done 或 error 后自动关闭连接。
 *
 * @param {string} path       - WebSocket 路径，如 /ws/workspaces/xxx/run
 * @param {object} payload
 * @param {Function} onChunk  - 每条非 done 事件回调
 * @param {Function} onDone   - 收到 done 或连接关闭时回调
 * @param {Function} onError  - 收到 error 事件或连接异常时回调
 * @returns {WebSocket}       - 返回 ws 实例，外部可调用 ws.close() 中止
 */
export function wsRun(path, payload, onChunk, onDone, onError) {
  const token = getAuthToken()
  const wsPath = token ? appendQuery(path, 'token', token) : path
  const ws = new WebSocket(resolveWebSocketUrl(wsPath))
  let completed = false

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
      completed = true
      onDone?.()
      ws.close()
      return
    }
    if (data.type === 'error') {
      completed = true
      onError?.(new Error(data.message ?? 'WebSocket error'))
      ws.close()
      return
    }
    onChunk?.(data)
  }

  ws.onerror = () => {
    completed = true
    onError?.(new Error('WebSocket 连接异常'))
  }

  ws.onclose = () => {
    if (!completed) {
      completed = true
      onDone?.()
    }
  }

  return ws
}

function appendQuery(path, key, value) {
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}${encodeURIComponent(key)}=${encodeURIComponent(value)}`
}

export { AUTH_TOKEN_CHANGED_EVENT, AUTH_TOKEN_KEY, appendQuery, resolveWebSocketUrl }

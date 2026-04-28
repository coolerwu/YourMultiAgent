import { afterEach, describe, expect, it, vi } from 'vitest'

import { AUTH_TOKEN_CHANGED_EVENT, appendQuery, resolveWebSocketUrl, setAuthToken, wsRun } from './api'

class MockWebSocket {
  static instances = []

  constructor(url) {
    this.url = url
    this.onopen = null
    this.onmessage = null
    this.onerror = null
    this.onclose = null
    this.sent = []
    this.closed = false
    MockWebSocket.instances.push(this)
  }

  send(data) {
    this.sent.push(data)
  }

  close() {
    this.closed = true
  }
}

describe('resolveWebSocketUrl', () => {
  it('uses current origin when VITE_API_BASE_URL is empty', () => {
    expect(resolveWebSocketUrl('/ws/workspaces/demo/run')).toBe('ws://localhost:3000/ws/workspaces/demo/run')
  })
})

describe('wsRun', () => {
  afterEach(() => {
    MockWebSocket.instances = []
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  it('sends payload when socket opens', () => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    const ws = wsRun('/ws/workspaces/demo/run', { user_message: 'hello' })

    ws.onopen?.()

    expect(ws.sent).toEqual([JSON.stringify({ user_message: 'hello' })])
  })

  it('adds auth token to websocket url when present', () => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    setAuthToken('token demo')

    wsRun('/ws/workspaces/demo/run', { user_message: 'hello' })

    expect(MockWebSocket.instances[0].url).toBe('ws://localhost:3000/ws/workspaces/demo/run?token=token%20demo')
  })

  it('calls onDone when socket closes before done event', () => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    const onDone = vi.fn()

    const ws = wsRun('/ws/workspaces/demo/run', { user_message: 'hello' }, vi.fn(), onDone, vi.fn())
    ws.onclose?.({ code: 1000 })

    expect(onDone).toHaveBeenCalledTimes(1)
  })
})

describe('appendQuery', () => {
  it('preserves existing query params', () => {
    expect(appendQuery('/ws/worker?kind=remote', 'token', 'abc')).toBe('/ws/worker?kind=remote&token=abc')
  })
})

describe('setAuthToken', () => {
  it('emits a token changed event', () => {
    const listener = vi.fn()
    window.addEventListener(AUTH_TOKEN_CHANGED_EVENT, listener)

    setAuthToken('token-demo')

    expect(listener).toHaveBeenCalledTimes(1)
    expect(listener.mock.calls[0][0].detail).toEqual({ token: 'token-demo' })
    window.removeEventListener(AUTH_TOKEN_CHANGED_EVENT, listener)
  })
})

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LoginGate from './LoginGate'

const { authApiMock } = vi.hoisted(() => ({
  authApiMock: {
    status: vi.fn(),
    login: vi.fn(),
  },
}))

vi.mock('../utils/api', async () => {
  const actual = await vi.importActual('../utils/api')
  return {
    ...actual,
    authApi: authApiMock,
  }
})

describe('LoginGate', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  it('renders children when auth is disabled', async () => {
    authApiMock.status.mockResolvedValue({ enabled: false })

    render(<LoginGate><div>应用内容</div></LoginGate>)

    expect(await screen.findByText('应用内容')).toBeInTheDocument()
  })

  it('requires aksk login when auth is enabled', async () => {
    authApiMock.status.mockResolvedValue({ enabled: true, authenticated: false })
    authApiMock.login.mockResolvedValue({ token: 'token-demo', expires_at: 123 })

    render(<LoginGate><div>应用内容</div></LoginGate>)

    expect(await screen.findByText('登录 YourMultiAgent')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Access Key'), { target: { value: 'ak-demo' } })
    fireEvent.change(screen.getByLabelText('Secret Key'), { target: { value: 'sk-demo' } })
    fireEvent.click(screen.getByRole('button', { name: /登录/ }))

    await waitFor(() => {
      expect(authApiMock.login).toHaveBeenCalledWith({ access_key: 'ak-demo', secret_key: 'sk-demo' })
    })
    expect(await screen.findByText('应用内容')).toBeInTheDocument()
    expect(window.localStorage.getItem('yourmultiagent-auth-token')).toBe('token-demo')
  })

  it('does not trust a stale local token before backend status confirms it', async () => {
    window.localStorage.setItem('yourmultiagent-auth-token', 'stale-token')
    authApiMock.status.mockResolvedValue({ enabled: true, authenticated: false })

    render(<LoginGate><div>应用内容</div></LoginGate>)

    expect(await screen.findByText('登录 YourMultiAgent')).toBeInTheDocument()
    expect(screen.queryByText('应用内容')).not.toBeInTheDocument()
  })

  it('returns to login when a later api 401 clears the token', async () => {
    authApiMock.status.mockResolvedValue({ enabled: true, authenticated: true })

    render(<LoginGate><div>应用内容</div></LoginGate>)

    expect(await screen.findByText('应用内容')).toBeInTheDocument()
    window.dispatchEvent(new CustomEvent('yourmultiagent-auth-token-changed', { detail: { token: '' } }))

    expect(await screen.findByText('登录 YourMultiAgent')).toBeInTheDocument()
  })
})

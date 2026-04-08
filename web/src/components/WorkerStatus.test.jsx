import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkerStatus from './WorkerStatus'

const { workerApiMock } = vi.hoisted(() => ({
  workerApiMock: {
    listWorkers: vi.fn(),
    updateEnabledCapabilities: vi.fn(),
  },
}))

vi.mock('../utils/graphApi', () => ({
  workerApi: workerApiMock,
}))

describe('WorkerStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    Object.defineProperty(window, 'getComputedStyle', {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        getPropertyValue: () => '',
      })),
    })
    workerApiMock.listWorkers.mockResolvedValue([
      {
        worker_id: 'browser-1',
        label: 'Chrome Web Client',
        kind: 'browser',
        status: 'online',
        version: '1.0.0',
        platform: 'macOS',
        browser_type: 'chromium',
        headless: true,
        allowed_origins: ['https://example.com'],
        max_sessions: 2,
        max_screenshot_bytes: 65536,
        max_text_chars: 2000,
        max_html_chars: 8000,
        source: '127.0.0.1:50123',
        connected_at: '2026-04-07T14:00:00Z',
        last_seen_at: '2026-04-07T14:05:00Z',
        last_error: '',
        enabled_capability_names: ['browser_open', 'browser_get_text'],
        registered_capabilities: [
          {
            name: 'browser_open',
            description: '打开页面',
            category: 'browser_read',
            risk_level: 'low',
            requires_session: false,
            parameters: [],
          },
          {
            name: 'browser_click',
            description: '点击元素',
            category: 'browser_write',
            risk_level: 'medium',
            requires_session: true,
            parameters: [],
          },
        ],
      },
    ])
    workerApiMock.updateEnabledCapabilities.mockResolvedValue({})
  })

  it('renders worker metadata and updates enabled capabilities', async () => {
    render(<WorkerStatus />)

    expect(await screen.findByText('Chrome Web Client')).toBeInTheDocument()
    expect(screen.getByText(/已授权 2 \/ 已注册 2/)).toBeInTheDocument()
    expect(screen.getByText('browser')).toBeInTheDocument()
    expect(screen.getByText(/允许域名：https:\/\/example.com/)).toBeInTheDocument()
    expect(screen.getByText(/chromium/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '只读浏览' }))

    await waitFor(() => {
      expect(workerApiMock.updateEnabledCapabilities).toHaveBeenCalledWith('browser-1', ['browser_open'])
    })
  })
})

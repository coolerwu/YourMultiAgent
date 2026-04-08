import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProviderManager from './ProviderManager'

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getProviderSettings: vi.fn(),
    getCodexRuntimeSummary: vi.fn(),
    updateProviderSettings: vi.fn(),
    checkCodexConnection: vi.fn(),
    installCodexConnection: vi.fn(),
    loginCodexConnection: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

describe('ProviderManager', () => {
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
    workspaceApiMock.getProviderSettings.mockResolvedValue({
      default_provider: 'anthropic',
      default_model: 'claude-sonnet-4-6',
      llm_profiles: [],
      codex_connections: [],
    })
    workspaceApiMock.getCodexRuntimeSummary.mockResolvedValue({
      os_family: 'macOS',
      node_path: '/usr/local/bin/node',
      npm_path: '/usr/local/bin/npm',
      codex_path: '',
      codex_version: '',
    })
    workspaceApiMock.updateProviderSettings.mockResolvedValue({
      default_provider: 'anthropic',
      default_model: 'claude-sonnet-4-6',
      llm_profiles: [],
      codex_connections: [],
    })
  })

  it('renders embedded provider page without update-now entry', async () => {
    render(<ProviderManager embedded />)

    expect(await screen.findByText('全局模型连接')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Update Now/ })).not.toBeInTheDocument()
  })
})

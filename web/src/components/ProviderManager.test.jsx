import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProviderManager, { buildProviderSettingsPayload } from './ProviderManager'

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
      llm_profiles: [],
      codex_connections: [],
    })
  })

  it('renders embedded provider page without update-now entry', async () => {
    render(<ProviderManager embedded />)

    expect(await screen.findByText('全局模型连接')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Update Now/ })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('默认 Provider')).not.toBeInTheDocument()
  })

  it('keeps api providers as a pure list without default fields', async () => {
    render(<ProviderManager embedded />)

    expect((await screen.findAllByText('共享 API Providers')).length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole('button', { name: /添加 Provider$/ })[0])

    expect(await screen.findByLabelText('名称')).toHaveValue('claude-sonnet-4-6')
    expect(screen.getByLabelText('Provider 类型')).toBeInTheDocument()
    expect(screen.getByLabelText('模型')).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toBeInTheDocument()
  })

  it('only submits editable codex config fields when saving', async () => {
    const payload = buildProviderSettingsPayload({
      llm_profiles: [],
      codex_connections: [{
        id: 'codex-1',
        name: '个人 Codex',
        status: 'connected',
        login_status: 'connected',
        install_status: 'installed',
        account_label: 'ChatGPT',
        install_path: '/usr/local/bin/codex',
        provider: 'openai_codex',
        auth_mode: 'chatgpt_codex_login',
      }],
    })

    expect(payload).toEqual({
      llm_profiles: [],
      codex_connections: [{
        id: 'codex-1',
        name: '个人 Codex',
        provider: 'openai_codex',
        auth_mode: 'chatgpt_codex_login',
      }],
    })
    expect(payload.codex_connections[0]).not.toHaveProperty('login_status')
    expect(payload.codex_connections[0]).not.toHaveProperty('install_status')
    expect(payload.codex_connections[0]).not.toHaveProperty('status')
  })
})

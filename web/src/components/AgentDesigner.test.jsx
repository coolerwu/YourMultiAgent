import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AgentDesigner from './AgentDesigner'

const { graphApiMock, workerApiMock } = vi.hoisted(() => ({
  graphApiMock: {
    create: vi.fn(),
    update: vi.fn(),
    optimizePrompt: vi.fn(),
  },
  workerApiMock: {
    listCapabilities: vi.fn(),
  },
}))

vi.mock('@xyflow/react', () => ({
  Background: () => null,
  Controls: () => null,
  Handle: () => null,
  MiniMap: () => null,
  Position: { Left: 'left', Right: 'right' },
  ReactFlow: ({ children }) => <div>{children}</div>,
  addEdge: (_edge, edges) => edges,
  useEdgesState: (initial) => [initial, vi.fn(), vi.fn()],
  useNodesState: (initial) => [initial, vi.fn(), vi.fn()],
}))

vi.mock('../utils/graphApi', () => ({
  graphApi: graphApiMock,
  workerApi: workerApiMock,
}))

describe('AgentDesigner', () => {
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
    workerApiMock.listCapabilities.mockResolvedValue([])
  })

  it('switches agent editor to codex-specific fields after selecting codex type', async () => {
    render(
      <AgentDesigner
        graph={null}
        workspaceId="ws-1"
        workspaceDefaults={{
          llm_profiles: [{
            id: 'llm-1',
            name: 'Claude 主力',
            provider: 'anthropic',
            model: 'claude-sonnet-4-6',
            base_url: '',
            api_key: '',
          }],
          codex_connections: [{ id: 'codex-1', name: '个人 Codex' }],
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '+ 添加节点' }))

    expect(await screen.findByText('编辑 Agent')).toBeInTheDocument()
    expect(screen.getByLabelText('模型类型')).toBeInTheDocument()
    expect(screen.queryByLabelText('Codex 登录连接')).not.toBeInTheDocument()
    expect(screen.getByLabelText('API Provider')).toBeInTheDocument()
    expect(screen.queryByText('通用 LLM 配置')).not.toBeInTheDocument()

    fireEvent.mouseDown(screen.getByLabelText('模型类型'))
    fireEvent.click(await screen.findByText('Codex'))

    expect(await screen.findByLabelText('Codex 登录连接')).toBeInTheDocument()
  })
})

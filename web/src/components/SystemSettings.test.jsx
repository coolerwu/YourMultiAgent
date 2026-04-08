import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SystemSettings from './SystemSettings'

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getUpdateNowStatus: vi.fn(),
    startUpdateNow: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

describe('SystemSettings', () => {
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
    workspaceApiMock.getUpdateNowStatus.mockResolvedValue({
      status: 'idle',
      logs: [],
      steps: [],
      error: '',
    })
    workspaceApiMock.startUpdateNow.mockResolvedValue({
      status: 'running',
      logs: ['开始执行 Update Now'],
      steps: [{ name: 'git_pull', status: 'running', summary: '' }],
      error: '',
    })
  })

  it('starts update now from system settings page', async () => {
    render(<SystemSettings />)

    expect(await screen.findByText('系统设置')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Update Now/ }))
    fireEvent.click(await screen.findByRole('button', { name: '开始更新' }))

    await waitFor(() => {
      expect(workspaceApiMock.startUpdateNow).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByText('Update Now 执行中')).toBeInTheDocument()
  })
})

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AppLogViewer from './AppLogViewer'

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getAppLog: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

describe('AppLogViewer', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    workspaceApiMock.getAppLog.mockResolvedValue({
      filename: 'app.log',
      path: '/tmp/app.log',
      content: '2026-04-08 10:00:00 [INFO] app - ai_request',
      line_count: 12,
      exists: true,
    })
  })

  it('renders app log as a standalone page', async () => {
    render(<AppLogViewer />)

    expect(await screen.findByText('应用日志')).toBeInTheDocument()
    expect(await screen.findByText(/当前只保留一个应用日志文件：app\.log/)).toBeInTheDocument()
    expect(await screen.findByTestId('system-app-log')).toHaveTextContent('ai_request')
  })
})

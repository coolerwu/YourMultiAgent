/**
 * worker_client/src/browserWorkerClient.js
 *
 * 基于 Playwright 的浏览器 Remote Worker。
 * 连接 Central Server 后通过 WebSocket 注册 browser_* capabilities。
 */

import os from 'node:os'

const DEFAULT_TEXT_LIMIT = 4000
const DEFAULT_HTML_LIMIT = 12000
const DEFAULT_SCREENSHOT_LIMIT_BYTES = 1024 * 1024
const DEFAULT_MAX_SESSIONS = 3

export const CAPABILITIES = [
  {
    name: 'browser_open',
    description: '打开页面并返回 session_id',
    category: 'browser_read',
    risk_level: 'low',
    requires_session: false,
    description_for_model: '打开网页，必要时创建新的浏览器会话，并返回 session_id。',
    parameters: [
      { name: 'url', type: 'string', description: '目标 URL', required: true },
      { name: 'session_id', type: 'string', description: '已有会话 ID，可选', required: false, default: '' }
    ]
  },
  {
    name: 'browser_close',
    description: '关闭指定浏览器会话',
    category: 'browser_session',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '关闭已有浏览器会话。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true }
    ]
  },
  {
    name: 'browser_get_text',
    description: '读取页面或元素文本',
    category: 'browser_read',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '读取整个页面或指定元素的文本内容。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: '可选 CSS 选择器', required: false, default: '' }
    ]
  },
  {
    name: 'browser_get_title',
    description: '读取页面标题',
    category: 'browser_read',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '读取当前页面标题。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true }
    ]
  },
  {
    name: 'browser_get_html',
    description: '读取页面 HTML',
    category: 'browser_read',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '读取当前页面 HTML 或指定元素 outerHTML。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: '可选 CSS 选择器', required: false, default: '' }
    ]
  },
  {
    name: 'browser_click',
    description: '点击页面元素',
    category: 'browser_write',
    risk_level: 'medium',
    requires_session: true,
    description_for_model: '点击指定页面元素。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: 'CSS 选择器', required: true }
    ]
  },
  {
    name: 'browser_type',
    description: '向输入框填写文本',
    category: 'browser_write',
    risk_level: 'medium',
    requires_session: true,
    description_for_model: '向指定输入框清空后填写文本。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: 'CSS 选择器', required: true },
      { name: 'text', type: 'string', description: '要输入的文本', required: true }
    ]
  },
  {
    name: 'browser_press',
    description: '向页面元素发送键盘按键',
    category: 'browser_write',
    risk_level: 'medium',
    requires_session: true,
    description_for_model: '向指定元素发送键盘按键，例如 Enter。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: 'CSS 选择器', required: true },
      { name: 'key', type: 'string', description: '按键名', required: true }
    ]
  },
  {
    name: 'browser_wait_for',
    description: '等待元素出现或页面完成加载',
    category: 'browser_session',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '等待页面达到指定状态，或等待某个元素出现。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: '可选 CSS 选择器', required: false, default: '' },
      { name: 'timeout_ms', type: 'integer', description: '超时时间毫秒', required: false, default: 10000 }
    ]
  },
  {
    name: 'browser_exists',
    description: '判断元素是否存在',
    category: 'browser_read',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '判断页面中是否存在指定元素。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'selector', type: 'string', description: 'CSS 选择器', required: true }
    ]
  },
  {
    name: 'browser_screenshot',
    description: '截取页面截图',
    category: 'browser_debug',
    risk_level: 'low',
    requires_session: true,
    description_for_model: '截取当前页面截图，返回 base64 PNG。',
    parameters: [
      { name: 'session_id', type: 'string', description: '会话 ID', required: true },
      { name: 'full_page', type: 'boolean', description: '是否整页截图', required: false, default: true }
    ]
  }
]

function resolveWsUrl(serverUrl) {
  const base = serverUrl.replace(/\/$/, '')
  return `${base}/ws/worker`
}

function normalizeTimeout(value, fallback = 10000) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return parsed
}

function truncateText(value, limit) {
  const text = String(value ?? '')
  if (text.length <= limit) {
    return { value: text, truncated: false }
  }
  return {
    value: `${text.slice(0, limit)}\n...[truncated ${text.length - limit} chars]`,
    truncated: true
  }
}

async function createDefaultWebSocket(url) {
  const { default: WebSocket } = await import('ws')
  return new WebSocket(url)
}

async function createDefaultBrowserLauncher(browserType, headless) {
  const { chromium, firefox, webkit } = await import('playwright')
  const launcher = { chromium, firefox, webkit }[browserType]
  if (!launcher) {
    throw new Error(`不支持的浏览器类型: ${browserType}`)
  }
  return launcher.launch({ headless })
}

export class BrowserWorkerClient {
  constructor(options) {
    this._server = options.server
    this._name = options.name || os.hostname()
    this._label = options.label || this._name
    this._browserType = options.browserType || 'chromium'
    this._headless = options.headless !== false
    this._allowedOrigins = options.allowedOrigins || []
    this._maxSessions = normalizeTimeout(options.maxSessions, DEFAULT_MAX_SESSIONS)
    this._maxScreenshotBytes = normalizeTimeout(options.maxScreenshotBytes, DEFAULT_SCREENSHOT_LIMIT_BYTES)
    this._maxTextChars = normalizeTimeout(options.maxTextChars, DEFAULT_TEXT_LIMIT)
    this._maxHtmlChars = normalizeTimeout(options.maxHtmlChars, DEFAULT_HTML_LIMIT)
    this._wsFactory = options.wsFactory || createDefaultWebSocket
    this._browserFactory = options.browserFactory || ((browserType, headless) => createDefaultBrowserLauncher(browserType, headless))
    this._ws = null
    this._browser = null
    this._sessions = new Map()
    this._lastError = ''
  }

  buildRegisterPayload() {
    return {
      type: 'register',
      worker_id: this._name,
      worker_meta: {
        kind: 'browser',
        label: this._label,
        version: '0.1.0',
        platform: `${os.platform()}-${os.arch()}`,
        browser_type: this._browserType,
        headless: this._headless,
        allowed_origins: this._allowedOrigins,
        max_sessions: this._maxSessions,
        max_screenshot_bytes: this._maxScreenshotBytes,
        max_text_chars: this._maxTextChars,
        max_html_chars: this._maxHtmlChars,
      },
      capabilities: CAPABILITIES.map((item) => ({ ...item, worker_id: this._name }))
    }
  }

  async start() {
    await this._connectLoop()
  }

  async _connectLoop() {
    while (true) {
      try {
        await this._runOnce()
      } catch (error) {
        this._lastError = error?.message || String(error)
        console.error(`[browser-worker] 连接异常: ${this._lastError}`)
      }
      await this._closeAllSessions()
      await new Promise((resolve) => setTimeout(resolve, 5000))
    }
  }

  async _runOnce() {
    const url = resolveWsUrl(this._server)
    console.log(`[browser-worker] connecting ${url}`)

    await new Promise(async (resolve, reject) => {
      try {
        const ws = await this._wsFactory(url)
        this._ws = ws

        ws.once('open', () => {
          try {
            ws.send(JSON.stringify(this.buildRegisterPayload()))
          } catch (error) {
            reject(error)
          }
        })

        ws.once('message', (raw) => {
          try {
            const data = JSON.parse(String(raw))
            if (data.type !== 'registered') {
              reject(new Error(`注册失败: ${String(raw)}`))
              return
            }
            console.log(`[browser-worker] registered ${this._name}, enabled=${data.enabled_capabilities_count ?? data.capabilities_count}`)
            resolve()
          } catch (error) {
            reject(error)
          }
        })

        ws.once('error', reject)
      } catch (error) {
        reject(error)
      }
    })

    await new Promise((resolve, reject) => {
      const ws = this._ws
      if (!ws) {
        reject(new Error('WebSocket 未初始化'))
        return
      }

      ws.on('message', async (raw) => {
        const msg = JSON.parse(String(raw))
        if (msg.type !== 'invoke') return
        await this._handleInvoke(msg)
      })

      ws.once('close', resolve)
      ws.once('error', reject)
    })
  }

  async _handleInvoke(msg) {
    const requestId = msg.request_id
    try {
      const result = await this._invokeCapability(msg.capability, msg.params || {})
      this._ws?.send(JSON.stringify({
        type: 'result',
        request_id: requestId,
        result,
        error: null
      }))
    } catch (error) {
      this._lastError = error?.message || String(error)
      this._ws?.send(JSON.stringify({
        type: 'result',
        request_id: requestId,
        result: null,
        error: this._lastError
      }))
    }
  }

  async _invokeCapability(name, params) {
    switch (name) {
      case 'browser_open':
        return this._browserOpen(params)
      case 'browser_close':
        return this._browserClose(params)
      case 'browser_get_text':
        return this._browserGetText(params)
      case 'browser_get_title':
        return this._browserGetTitle(params)
      case 'browser_get_html':
        return this._browserGetHtml(params)
      case 'browser_click':
        return this._browserClick(params)
      case 'browser_type':
        return this._browserTypeText(params)
      case 'browser_press':
        return this._browserPress(params)
      case 'browser_wait_for':
        return this._browserWaitFor(params)
      case 'browser_exists':
        return this._browserExists(params)
      case 'browser_screenshot':
        return this._browserScreenshot(params)
      default:
        throw new Error(`未知 capability: ${name}`)
    }
  }

  async _getBrowser() {
    if (this._browser) return this._browser
    this._browser = await this._browserFactory(this._browserType, this._headless)
    return this._browser
  }

  _assertUrlAllowed(url) {
    if (this._allowedOrigins.length === 0) return
    const origin = new URL(url).origin
    if (!this._allowedOrigins.includes(origin)) {
      throw new Error(`URL origin 不在允许列表内: ${origin}`)
    }
  }

  async _assertSessionOriginAllowed(session) {
    const currentUrl = session.page.url?.() || ''
    if (!currentUrl || currentUrl === 'about:blank') return
    this._assertUrlAllowed(currentUrl)
  }

  async _getSession(sessionId) {
    if (!sessionId || !this._sessions.has(sessionId)) {
      throw new Error(`会话不存在: ${sessionId}`)
    }
    return this._sessions.get(sessionId)
  }

  _createSessionId() {
    return `browser_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  }

  async _browserOpen(params) {
    const url = String(params.url || '').trim()
    if (!url) throw new Error('url 不能为空')
    this._assertUrlAllowed(url)

    let sessionId = String(params.session_id || '').trim()
    let session = sessionId ? this._sessions.get(sessionId) : null
    if (!session) {
      if (this._sessions.size >= this._maxSessions) {
        throw new Error(`会话数已达上限: ${this._maxSessions}`)
      }
      const browser = await this._getBrowser()
      const context = await browser.newContext()
      const page = await context.newPage()
      sessionId = this._createSessionId()
      session = { context, page }
      this._sessions.set(sessionId, session)
    }

    await session.page.goto(url, { waitUntil: 'domcontentloaded' })
    return {
      session_id: sessionId,
      url: session.page.url(),
      title: await session.page.title()
    }
  }

  async _browserClose(params) {
    const sessionId = String(params.session_id || '').trim()
    const session = await this._getSession(sessionId)
    await session.context.close()
    this._sessions.delete(sessionId)
    return { success: true, session_id: sessionId }
  }

  async _browserGetText(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    const text = !selector
      ? await session.page.locator('body').innerText()
      : await session.page.locator(selector).innerText()
    const output = truncateText(text, this._maxTextChars)
    return { text: output.value, selector, truncated: output.truncated }
  }

  async _browserGetTitle(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const output = truncateText(await session.page.title(), this._maxTextChars)
    return { title: output.value, truncated: output.truncated }
  }

  async _browserGetHtml(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    const html = !selector
      ? await session.page.content()
      : await session.page.locator(selector).evaluate((node) => node.outerHTML)
    const output = truncateText(html, this._maxHtmlChars)
    return { html: output.value, selector, truncated: output.truncated }
  }

  async _browserClick(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    if (!selector) throw new Error('selector 不能为空')
    await this._assertSessionOriginAllowed(session)
    await session.page.locator(selector).click()
    return { success: true, selector }
  }

  async _browserTypeText(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    const text = String(params.text || '')
    if (!selector) throw new Error('selector 不能为空')
    await this._assertSessionOriginAllowed(session)
    await session.page.locator(selector).fill(text)
    return { success: true, selector }
  }

  async _browserPress(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    const key = String(params.key || '').trim()
    if (!selector || !key) throw new Error('selector 和 key 不能为空')
    await this._assertSessionOriginAllowed(session)
    await session.page.locator(selector).press(key)
    return { success: true, selector, key }
  }

  async _browserWaitFor(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    const timeout = normalizeTimeout(params.timeout_ms)
    if (!selector) {
      await session.page.waitForLoadState('networkidle', { timeout })
      return { success: true, waited_for: 'networkidle', timeout_ms: timeout }
    }
    await session.page.locator(selector).waitFor({ state: 'visible', timeout })
    return { success: true, selector, timeout_ms: timeout }
  }

  async _browserExists(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const selector = String(params.selector || '').trim()
    if (!selector) throw new Error('selector 不能为空')
    const count = await session.page.locator(selector).count()
    return { exists: count > 0, count, selector }
  }

  async _browserScreenshot(params) {
    const session = await this._getSession(String(params.session_id || '').trim())
    const fullPage = params.full_page !== false
    const bytes = await session.page.screenshot({ type: 'png', fullPage })
    const buffer = Buffer.from(bytes)
    if (buffer.byteLength > this._maxScreenshotBytes) {
      throw new Error(`截图结果超过限制: ${buffer.byteLength} > ${this._maxScreenshotBytes}`)
    }
    return {
      content_base64: buffer.toString('base64'),
      mime_type: 'image/png',
      byte_length: buffer.byteLength
    }
  }

  async _closeAllSessions() {
    for (const [sessionId, session] of this._sessions.entries()) {
      try {
        await session.context.close()
      } catch (_) {
        // ignore close error
      }
      this._sessions.delete(sessionId)
    }
    if (this._browser) {
      try {
        await this._browser.close()
      } catch (_) {
        // ignore close error
      }
      this._browser = null
    }
  }
}

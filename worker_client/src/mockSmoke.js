/**
 * worker_client/src/mockSmoke.js
 *
 * 不依赖真实浏览器和真实 WebSocket 服务的主链路 smoke 校验。
 */

import process from 'node:process'
import { BrowserWorkerClient } from './browserWorkerClient.js'

class FakeLocator {
  constructor(page, selector) {
    this._page = page
    this._selector = selector
  }

  async innerText() {
    if (this._selector === 'body') return this._page.bodyText
    return this._page.nodeText[this._selector] || ''
  }

  async evaluate(fn) {
    return fn({ outerHTML: this._page.nodeHtml[this._selector] || '<div></div>' })
  }

  async click() {
    this._page.clicks.push(this._selector)
  }

  async fill(text) {
    this._page.fills.push({ selector: this._selector, text })
  }

  async press(key) {
    this._page.presses.push({ selector: this._selector, key })
  }

  async waitFor() {
    return true
  }

  async count() {
    return this._page.nodeText[this._selector] ? 1 : 0
  }
}

class FakePage {
  constructor() {
    this.currentUrl = 'about:blank'
    this.bodyText = 'body text'
    this.nodeText = { '#submit': 'Submit', '#content': 'Hello worker' }
    this.nodeHtml = { '#content': '<div id="content">Hello worker</div>' }
    this.clicks = []
    this.fills = []
    this.presses = []
  }

  async goto(url) {
    this.currentUrl = url
  }

  url() {
    return this.currentUrl
  }

  async title() {
    return 'Demo title'
  }

  locator(selector) {
    return new FakeLocator(this, selector)
  }

  async content() {
    return '<html><body>Hello worker</body></html>'
  }

  async waitForLoadState() {
    return true
  }

  async screenshot() {
    return Buffer.from('fake-png')
  }
}

class FakeContext {
  constructor(page) {
    this.page = page
    this.closed = false
  }

  async newPage() {
    return this.page
  }

  async close() {
    this.closed = true
  }
}

class FakeBrowser {
  constructor(page) {
    this.page = page
  }

  async newContext() {
    return new FakeContext(this.page)
  }

  async close() {
    return true
  }
}

async function main() {
  const fakePage = new FakePage()
  const client = new BrowserWorkerClient({
    server: 'ws://localhost:8080',
    name: 'mock-browser-worker',
    allowedOrigins: ['https://example.com'],
    browserFactory: async () => new FakeBrowser(fakePage),
  })

  const open = await client._invokeCapability('browser_open', { url: 'https://example.com/demo' })
  const sessionId = open.session_id
  const waited = await client._invokeCapability('browser_wait_for', { session_id: sessionId, selector: '#content' })
  const clicked = await client._invokeCapability('browser_click', { session_id: sessionId, selector: '#submit' })
  const text = await client._invokeCapability('browser_get_text', { session_id: sessionId, selector: '#content' })
  const closed = await client._invokeCapability('browser_close', { session_id: sessionId })

  if (!sessionId || !waited.success || !clicked.success || text.text !== 'Hello worker' || !closed.success) {
    throw new Error('mock smoke 校验失败')
  }

  console.log('mock smoke passed')
}

main().catch((error) => {
  console.error(error?.stack || error)
  process.exit(1)
})

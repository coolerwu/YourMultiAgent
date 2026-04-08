#!/usr/bin/env node
/**
 * worker_client/src/cli.js
 *
 * npm 可执行的浏览器 Worker CLI。
 */

import os from 'node:os'
import process from 'node:process'
import { BrowserWorkerClient } from './browserWorkerClient.js'

function printHelp() {
  console.log(`
YourMultiAgent Browser Worker

Usage:
  yourmultiagent-browser-worker --server ws://localhost:8080 [options]

Options:
  --server <url>            Central Server 地址，必填
  --name <worker-id>        Worker ID，默认主机名
  --label <label>           Worker 展示名，默认同 name
  --browser <type>          chromium | firefox | webkit，默认 chromium
  --headed                  使用有头浏览器，默认 headless
  --allow-origin <origin>   允许访问的 origin，可重复传入
  --max-sessions <n>        最大会话数，默认 3
  --max-screenshot-kb <n>   截图返回上限，默认 1024 KB
  --max-text-chars <n>      文本返回上限，默认 4000
  --max-html-chars <n>      HTML 返回上限，默认 12000
  --help                    显示帮助
`)
}

function parseArgs(argv) {
  const result = {
    server: '',
    name: os.hostname(),
    label: '',
    browserType: 'chromium',
    headless: true,
    allowedOrigins: [],
    maxSessions: 3,
    maxScreenshotBytes: 1024 * 1024,
    maxTextChars: 4000,
    maxHtmlChars: 12000,
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    const next = argv[index + 1]

    if (arg === '--help' || arg === '-h') {
      result.help = true
      continue
    }
    if (arg === '--headed') {
      result.headless = false
      continue
    }
    if (arg === '--server') {
      result.server = next || ''
      index += 1
      continue
    }
    if (arg === '--name') {
      result.name = next || result.name
      index += 1
      continue
    }
    if (arg === '--label') {
      result.label = next || ''
      index += 1
      continue
    }
    if (arg === '--browser') {
      result.browserType = next || 'chromium'
      index += 1
      continue
    }
    if (arg === '--allow-origin') {
      if (next) result.allowedOrigins.push(next)
      index += 1
      continue
    }
    if (arg === '--max-sessions') {
      result.maxSessions = Number(next || 3)
      index += 1
      continue
    }
    if (arg === '--max-screenshot-kb') {
      result.maxScreenshotBytes = Number(next || 1024) * 1024
      index += 1
      continue
    }
    if (arg === '--max-text-chars') {
      result.maxTextChars = Number(next || 4000)
      index += 1
      continue
    }
    if (arg === '--max-html-chars') {
      result.maxHtmlChars = Number(next || 12000)
      index += 1
    }
  }

  return result
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (options.help || !options.server) {
    printHelp()
    process.exit(options.help ? 0 : 1)
  }

  const client = new BrowserWorkerClient(options)
  await client.start()
}

main().catch((error) => {
  console.error(`[browser-worker] fatal: ${error?.stack || error}`)
  process.exit(1)
})

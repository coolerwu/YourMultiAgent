# worker_client

可独立发布为 npm 包的浏览器 Worker 客户端。启动后会通过 WebSocket 注册到 YourMultiAgent 大脑，并暴露 `browser_*` 能力。

## 安装

```bash
cd worker_client
npm install
npx playwright install chromium
npm run smoke:mock
```

## 运行

```bash
npx yourmultiagent-browser-worker \
  --server ws://localhost:8080 \
  --name browser-worker-1 \
  --label "Chrome Web Client"
```

## 参数

- `--server`：Central Server 地址，必填
- `--name`：Worker ID，默认主机名
- `--label`：页面展示名
- `--browser`：`chromium` / `firefox` / `webkit`
- `--headed`：以有头模式启动浏览器
- `--allow-origin`：限制允许访问的 origin，可重复传入
- `--max-sessions`：最大会话数
- `--max-screenshot-kb`：截图返回体上限
- `--max-text-chars`：文本返回字符上限
- `--max-html-chars`：HTML 返回字符上限

## 校验

```bash
npm run check
npm run smoke:mock
```

`smoke:mock` 不依赖真实浏览器和真实服务端，会模拟一条 `browser_open -> browser_wait_for -> browser_click -> browser_get_text -> browser_close` 主链路。

## 当前能力

- `browser_open`
- `browser_close`
- `browser_get_text`
- `browser_get_title`
- `browser_get_html`
- `browser_click`
- `browser_type`
- `browser_press`
- `browser_wait_for`
- `browser_exists`
- `browser_screenshot`

所有交互型能力都围绕 `session_id` 工作，因此可被大脑多轮复用同一个浏览器会话。

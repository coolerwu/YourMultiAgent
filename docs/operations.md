# 运维与运行时

本文档说明当前项目中的系统级运维入口，以及宿主机上 Codex CLI 的运行方式。

## 系统设置

页面左侧提供 `系统设置` 入口，当前包含两类能力：

- `全局模型连接`
  - `API Providers` 只有共享列表，没有默认 Provider
  - 每个 Provider 项显式维护 `名称 / Provider 类型 / 模型 / URL / API Key`
  - 所有使用 LLM 的角色都必须显式绑定某个 `API Provider`

- `Update Now`
  - 对当前应用执行增量更新
  - 流程为：`git fetch/pull` -> 同步 Python 依赖 -> 重启服务
  - 会造成一次短暂服务重启，不是热更新
- `Codex 运行时`
  - 检测当前宿主机的 Codex CLI 安装、版本、路径和登录状态
  - 支持 `检测环境`、`安装/更新 Codex`、`登录 Codex`
- `应用日志`
  - 直接展示宿主机当前唯一的 `app.log`
  - 统一记录 HTTP、WebSocket、Worker、Store、AI、系统设置与 `uvicorn` 访问事件
  - 页面默认展示最近 300 行

## Codex 运行时模型

当前实现里，Codex CLI 是“宿主机全局运行时”，不是“每个连接独立一套运行时”。

这意味着：

- 同一台宿主机上只维护一份 `codex` CLI 安装
- `codex login` 登录态也是宿主机全局状态
- 页面里的多个 Codex 连接目前主要承担“配置引用”和“状态呈现”作用
- 当前不支持在同一台宿主机上同时维持多个独立 ChatGPT Codex 账号登录态

如果未来需要真正多账号并存，必须引入新的隔离模型，例如：

- 不同系统用户分别登录不同 Codex 账号
- 不同容器 / 不同工作目录隔离各自的登录态与配置目录
- 后端显式为每个连接指定独立的配置目录和执行环境

当前版本未实现上述隔离能力。

## 应用日志

当前系统日志策略如下：

- 只保留一个主日志文件：`app.log`
- 不再拆分出额外业务日志文件
- 日志内容仅保留最近 3 天
- 前端 `系统设置 -> 应用日志` 直接读取该文件尾部内容

当前会写入的关键事件包括：

- HTTP 请求开始/结束/异常
- WebSocket 连接、Workspace 运行与 Remote Worker 注册
- Worker capability 调用、全局设置与 workspace/store 读写
- LLM 请求/响应摘要、工具调用与运行异常
- `uvicorn` access/error 日志

如果页面运行卡住，可先查看 `app.log` 中最后一段 `http_request_error`、`workspace_run_failed`、`ai_error`、`tool_call` 或 `http_access` 记录定位。

## API Providers

当前 API Provider 策略如下：

- 不再维护 `默认 Provider / 默认模型 / 默认 URL / 默认 API Key`
- 全局只保留 `API Providers` 列表和 `Codex 登录连接` 列表
- 新增 Provider 时，名称会先按“模型 + URL”自动填充，但允许用户自行改名
- LLM 角色保存时必须带明确的 `llm_profile_id`
- 如果一个 Workspace 里没有任何 API Provider，则 LLM 角色无法完成绑定和保存

这意味着运行时解析顺序也随之收敛：

- 优先读取角色自身的 `llm_profile_id`
- 再从全局 `llm_profiles` 中解析 provider/model/base_url/api_key
- 仅在角色节点显式填写覆盖字段时才覆盖列表项值

## Codex 安装与登录

系统设置中的 `安装 Codex` / `更新 Codex` 走用户目录安装，不依赖 root，当前使用：

```bash
npm install -g @openai/codex --prefix ~/.local
```

安装完成后，前端会提示：

1. 退出终端
2. 重新进入终端
3. 执行 `codex login --device-auth`

原因是部分系统在当前 shell 中还没有刷新到新的 `PATH`，重新进入终端最稳。

## Codex 认证冲突说明

后端调用 `codex exec` 时，会清理显式 `OPENAI_*` 认证环境变量，避免它们污染本地 `codex login` 登录态。

当前已处理的变量包括：

- `OPENAI_API_KEY`
- `OPENAI_AUTH_TOKEN`
- `OPENAI_BASE_URL`
- `OPENAI_API_BASE`
- `OPENAI_ORG_ID`
- `OPENAI_ORGANIZATION`
- `OPENAI_PROJECT`

这些变量会统一移除，不区分空值还是非空值。

## SOCKS 代理依赖

当前后端 HTTP 客户端依赖为 `httpx[socks]`，以支持通过 SOCKS 代理访问外部服务。

如果运行时出现：

```text
Using SOCKS proxy, but the 'socksio' package is not installed.
```

说明当前 Python 环境还是旧依赖，重新执行一次安装即可：

```bash
pip install -e .
```

# 运维与运行时

本文档说明当前项目中的系统级运维入口，以及宿主机上 Codex CLI 的运行方式。

## 系统设置

页面左侧提供 `系统设置` 入口，当前包含两类能力：

- `Update Now`
  - 对当前应用执行增量更新
  - 流程为：`git fetch/pull` -> 同步 Python 依赖 -> 重启服务
  - 会造成一次短暂服务重启，不是热更新
- `Codex 运行时`
  - 检测当前宿主机的 Codex CLI 安装、版本、路径和登录状态
  - 支持 `检测环境`、`安装/更新 Codex`、`登录 Codex`

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

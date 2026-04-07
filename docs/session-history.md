# Session History

## 概览

Workspace 运行链路支持多条历史会话。

- 每条会话使用 `session_id` 标识
- 未传 `session_id` 时，后端自动创建新会话
- 同一 `session_id` 的后续运行会复用历史摘要、memory 和最近消息窗口
- 会话数据当前持久化在对应 Workspace 的 `workspace.json`

## 持久化模型

Workspace 下新增会话结构：

- `ChatSessionEntity`
  - `id`
  - `title`
  - `created_at`
  - `updated_at`
  - `status`
  - `message_count`
  - `summary`
  - `memory_items`
  - `messages`
- `ChatMessageEntity`
  - `role`
  - `kind`
  - `content`
  - `actor_id`
  - `actor_name`
  - `node`
  - `created_at`
- `MemoryItemEntity`
  - `category`
  - `content`
  - `confidence`
  - `source_message_ids`
  - `updated_at`

## 运行时注入顺序

Agent 实际拿到的上下文按以下顺序拼装：

1. Agent 的 `system_prompt`
2. 会话 `summary`
3. 会话 `memory_items`
4. 最近消息窗口
5. 当前用户消息

这样做的目标是：

- 先给高密度上下文
- 再给稳定记忆
- 最后保留近场对话细节

## Compact

### 触发条件

- 当会话消息数超过 `24` 条时触发
- 最近 `12` 条消息保持原文，不参与压缩

### 执行方式

compact 优先使用 LLM 摘要，而不是简单截断。

输入包括：

- 旧摘要
- 最近窗口之前的历史消息

输出固定为五段结构化摘要：

- `【用户目标】`
- `【已完成】`
- `【关键约束】`
- `【重要文件】`
- `【待继续】`

### 失败回退

如果 LLM compact 失败，回退到规则式摘录压缩，保证会话不会因摘要失败而中断。

## Memory Auto

每轮运行结束后，系统会自动从最近消息窗口提取结构化 memory。

当前重点抽取：

- `goal`
- `constraint`
- `decision`
- `artifact`

当前策略是规则提取，不依赖向量库。

## 前端行为

运行页支持：

- 会话列表
- 新建会话
- 历史会话加载
- 删除会话
- 当前会话摘要展示
- 当前会话 memory 标签展示

发送消息时，前端始终携带当前 `session_id`。

## 当前边界

- memory 作用域仅限单个 Workspace 内的单条会话
- 不做跨 Workspace 共享记忆
- 不做向量检索
- 不接 SQLite
- 摘要和 memory 目前都由后端统一管理，前端只读展示

# Agents.md — YourMultiAgent

个人多 Agent 平台，支持通过页面配置 Agent 数量、交互模式，Worker 可本机内置或远程接入。

本文档供当前仓库内的通用编码 Agent 使用，目标是在不破坏现有结构的前提下，稳定推进后端、前端和多 Agent 协作能力。

## 项目结构

```text
YourMultiAgent/
├── .agents/skills/   # Codex / 通用 Agent 可发现的技能
├── server/          # Python FastAPI 后端（COLA 分层）
├── web/             # React 前端（编译输出到 server/web/）
└── .claude/
    └── skills/      # 项目级 Skills
```

详见：
- `docs/server-architecture.md`：后端容器级架构图（C4 Model Level 2）
- `docs/web-architecture.md`：前端容器级架构图（C4 Model Level 2）
- `docs/agent-model.md`：Agent / Worker 运行模型容器图（C4 Model Level 2）
- `docs/session-history.md`：Workspace 会话历史、compact 与 memory 机制

## 测试

```bash
# 后端（项目根目录执行）
pytest server/tests/ -v

# 前端
cd web && npx vitest run
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12, FastAPI, LangGraph |
| 前端 | React 19, Vite, Ant Design |
| LLM | OpenAI / Anthropic（页面可配置） |
| 持久化 | 内存（初期），后续按需接 SQLite |
| Worker 通信 | 内置 Local Worker（初期），WebSocket（远程扩展） |

## Agent 工作规范

- 回复默认使用中文，除非用户明确要求英文
- 优先先读代码和现有文档，再做方案判断，避免凭空假设
- 修改应尽量局部、最小化，保持与现有架构和命名一致
- 每次改动后自行做至少 3 轮静态检查：正确性、边界条件、可维护性
- 若能本地验证，则优先运行对应测试；若未验证，需明确说明
- 除非用户明确要求，禁止私自提交代码，但可以准备提交命令
- 禁止私自部署服务、重启进程、修改生产配置
- 发现脏工作区时，不回滚非自己改动；冲突明显时先停止并说明

## 启动方式

```bash
# 后端
cd server && python main.py        # http://localhost:8080

# 前端开发
cd web && npm run dev              # http://localhost:5173

# 前端构建（输出到 server/web/）
cd web && npm run build
```

## 协作约定

- 方案优先服从现有仓库结构，不随意引入新的基础设施层
- 后端遵守 COLA 分层，避免在接口层堆积业务逻辑
- 前端遵守既有页面和状态管理方式，避免无必要的大规模重构
- Agent 能力设计优先考虑可扩展性，但首版实现以可运行、可验证为先
- 涉及多 Worker 通信时，先保证本机内置 Worker 路径清晰，再扩远程接入
- `Agents.md` 只保留高层约定、入口说明和关键索引；当某一主题细节变多或主文档体量明显增大时，优先拆分到 `docs/*.md`，并在 `Agents.md` 中保留链接与简短摘要

## 会话与上下文

- Workspace 运行链路支持多条历史会话，每条会话使用 `session_id` 续聊
- 会话持久化仍使用 `workspace.json`，当前不引入 SQLite 或向量库
- 当会话消息超过阈值时，后端会自动执行 compact，将旧摘要与早期消息压缩为结构化摘要
- compact 摘要默认包含：用户目标、已完成、关键约束、重要文件、待继续
- 自动 memory 当前为结构化事实记忆，重点保留目标、约束、结论和文件路径
- 详细接口、触发阈值与运行时注入顺序见 `docs/session-history.md`

## 提交前检查

1. 相关功能是否有最小可验证路径。
2. 是否补充或更新了必要测试。
3. 是否破坏了 `server/` 与 `web/` 的既有边界。
4. 是否需要同步更新 `CLAUDE.md` 或 `docs/` 文档。

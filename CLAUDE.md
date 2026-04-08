# CLAUDE.md — YourMultiAgent

个人多 Agent 平台，支持通过页面配置 Agent 数量、交互模式，Worker 可本机内置或远程接入。

## 项目结构

```
YourMultiAgent/
├── server/          # Python FastAPI 后端（COLA 分层）
├── web/             # React 前端（编译输出到 server/web/）
└── .claude/
    └── skills/      # 项目级 Skills
```

详见：
- [@docs/server-architecture.md](docs/server-architecture.md) — 后端容器级架构图（C4 Model Level 2）
- [@docs/web-architecture.md](docs/web-architecture.md) — 前端容器级架构图（C4 Model Level 2）
- [@docs/agent-model.md](docs/agent-model.md) — Agent/Worker 运行模型容器图（C4 Model Level 2）
- [@docs/session-history.md](docs/session-history.md) — 会话历史、compact 与 memory 机制

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
| LLM | Anthropic Claude / OpenAI（页面可配置） |
| 持久化 | 内存（初期），后续按需接 SQLite |
| Worker 通信 | 内置 Local Worker（初期），WebSocket（远程扩展） |

## 开发规范

- 回复使用中文
- 每次修改代码后自我 Code Review 3 次
- 每次代码修改/方案提出，自检：这么做合理吗？有漏洞吗？符合业内常识吗？
- 除非明确要求，禁止提交代码，但可给出可执行的 git 命令
- 禁止私自部署服务或重启进程

## 启动方式

```bash
# 后端
cd server && python main.py        # http://localhost:8080

# 前端开发
cd web && npm run dev              # http://localhost:5173

# 前端构建（输出到 server/web/）
cd web && npm run build
```

## 提交规范

使用项目 `/commit-push` skill，它会：
1. Code Review 检查 bug 和边界 case
2. 补充前后端单测
3. 更新 CLAUDE.md（过大则拆分到 docs/）
4. Commit + Push

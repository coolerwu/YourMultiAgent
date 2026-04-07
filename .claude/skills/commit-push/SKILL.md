---
name: commit-push
description: YourMultiAgent 项目专用提交技能。当用户说"提交"、"commit"、"push"、"/commit-push" 时触发。执行完整的提交流程：代码 review、补充单测、更新 CLAUDE.md（过大则拆分到 docs/）、git commit + push。
---

# commit-push

## 执行流程

### Step 1：运行检查脚本

```bash
python3 .claude/skills/commit-push/scripts/check_and_test.py
```

脚本输出：
- 完整 git diff（staged + unstaged）
- 变更文件列表
- 缺少单测的模块列表
- CLAUDE.md 大小告警（超 200 行提示拆分）

### Step 2：Code Review（自检 3 次）

逐一审查 diff，针对每处变更判断：
1. 这么做合理吗？
2. 有没有 bug 或边界 case 遗漏？
3. 是否符合 COLA 分层规范（adapter → app → domain ← infra）？

发现问题直接修复，不跳过。

### Step 3：补充单测

根据脚本输出的缺测列表：

**后端（Python/pytest）**
- 路径规则：`server/tests/<对应层路径>/test_<文件名>.py`
- 覆盖：正常路径 + 边界 case + 异常路径
- 使用 `pytest` + `unittest.mock`，禁止访问真实外部依赖

**前端（React/Vitest）**
- 路径规则：`web/src/<同目录>/<组件名>.test.jsx`
- 覆盖：渲染、用户交互、API mock
- 使用 `@testing-library/react` + `vitest`

### Step 4：更新 CLAUDE.md

- 若本次变更影响架构、模型、约定，更新对应 CLAUDE.md
- 若 CLAUDE.md 超过 200 行：
  1. 将大段内容（架构详情/模型设计/规范细节）抽取到 `docs/<topic>.md`
  2. 在 CLAUDE.md 原位置替换为 `[@docs/<topic>.md](docs/<topic>.md)`
  3. 保持 CLAUDE.md 为索引文件，控制在 100 行以内

### Step 5：构建前端

```bash
cd web && npm run build
```

构建失败则停止，修复后重试，不跳过。构建产物输出到 `server/web/`，一并纳入提交。

### Step 6：Commit + Push

**直接使用 Bash 工具执行，不要把命令打印出来让用户自己跑。**

0. 确认 `.gitignore` 存在，避免 `__pycache__`、`node_modules`、`server/web/` 被提交
1. 用 Bash 工具按文件/目录 `git add`（禁止 `git add .` 或 `git add -A`）
2. 根据变更内容自动生成中文 commit message（说明 why，不是 what），用 Bash 工具执行 `git commit`
3. 用 Bash 工具执行 `git push`
4. 输出最终 commit hash 和 push 结果

## 硬性约束

- 禁止 `git add .` 或 `git add -A`
- 禁止 `--no-verify` 跳过 hooks
- 禁止 force push 到 main
- commit message 使用中文
- **每一步都用工具直接执行，不输出让用户手动运行的命令**

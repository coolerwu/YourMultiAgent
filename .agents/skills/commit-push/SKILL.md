---
name: commit-push
description: YourMultiAgent 项目专用提交技能。当用户说“提交”“commit”“push”或“/commit-push”时使用。执行完整提交流程：代码 review、补充单测、同步更新 README/Agents/docs、构建前端，并完成一次完整 commit 与 push。
---

# Commit Push

## 执行流程

### Step 1：运行检查脚本

```bash
python3 .agents/skills/commit-push/scripts/check_and_test.py
```

脚本输出：
- 完整 git diff（staged + unstaged）
- 变更文件列表
- 缺少单测的模块列表
- `CLAUDE.md` 大小告警（超 200 行提示拆分）

### Step 2：Code Review（自检 3 次）

逐一审查 diff，针对每处变更判断：
1. 这么做合理吗？
2. 有没有 bug 或边界 case 遗漏？
3. 是否符合 COLA 分层规范（`adapter -> app -> domain <- infra`）？

发现问题直接修复，不跳过。

### Step 3：补充单测

根据脚本输出的缺测列表：

后端（Python / pytest）
- 路径规则：`server/tests/<对应层路径>/test_<文件名>.py`
- 覆盖：正常路径 + 边界 case + 异常路径
- 使用 `pytest` + `unittest.mock`，禁止访问真实外部依赖

前端（React / Vitest）
- 路径规则：`web/src/<同目录>/<组件名>.test.jsx`
- 覆盖：渲染、用户交互、API mock
- 使用 `@testing-library/react` + `vitest`

### Step 4：更新项目文档

- 若本次变更影响功能、架构、模型、运维入口、协作约定，必须先更新文档再提交
- 默认至少检查并按需更新：
  - `README.md`
  - `Agents.md`
  - `docs/*.md`
- 如需兼容 Claude 工作流，再同步更新 `CLAUDE.md`
- 若主索引文档超过 200 行，将大段细节抽取到 `docs/<topic>.md`

### Step 5：构建前端

```bash
cd web && npm run build
```

构建失败则停止，修复后重试，不跳过。构建产物输出到 `server/web/`，是否提交以仓库当前约定为准。

### Step 6：Commit + Push

直接使用终端工具执行，不把命令甩给用户手动跑。

1. 确认 `.gitignore` 存在，避免 `__pycache__`、`node_modules` 等无关文件被提交
2. 按文件或目录精确 `git add`，禁止 `git add .` 与 `git add -A`
3. 提交前确认本次应提交的源码、测试、文档、前端构建产物已全部纳入，禁止把相关文件拆成多次零散提交
4. 根据变更内容生成中文 commit message，重点写 why，不只写 what
5. 执行 `git commit`
6. 执行 `git push`
7. 输出最终 commit hash 和 push 结果，并说明是否仍有未提交改动

## 硬性约束

- 禁止 `git add .` 或 `git add -A`
- 禁止 `--no-verify` 跳过 hooks
- 禁止 force push 到 `main`
- commit message 使用中文
- 同一轮用户确认的相关变更必须一次性完整提交：源码、测试、README、Agents、docs、以及仓库约定需要提交的构建产物
- 每一步都直接用工具执行

---
name: dev-standards
description: YourMultiAgent 项目开发规范速查。当新增文件、新增模块、修改代码、重构、设计 API、或用户问"怎么写/放哪里/命名规范"时触发。涵盖 COLA 分层约束、后端 Python 规范、前端 React 规范、命名约定、测试规范，以及每次代码改动后必须执行的测试与构建流程。
---

# dev-standards

## COLA 分层约束（最高优先级）

```
adapter → app → domain ← infra
```

| 层 | 职责 | 禁止 |
|----|------|------|
| `adapter/` | 协议转换（HTTP/WS → Command/Query） | 含业务逻辑 |
| `app/` | 流程编排，调用 domain service | 直接操作 infra |
| `domain/` | 核心业务规则，定义 Gateway 接口 | import infra/adapter/app |
| `infra/` | 实现 Gateway 接口，对接外部系统 | 调用 app/adapter |

**违规检查：** 每次新建文件，确认 import 路径不违反上述方向。

## 后端规范（Python 3.12）

### 命名约定
- 实体类：`XxxEntity`（如 `GraphEntity`）
- 命令对象：`XxxCmd`（如 `CreateGraphCmd`）
- 查询 VO：`XxxVO`（如 `GraphVO`）
- 应用服务：`xxx_app_service.py`
- Gateway 接口：`xxx_gateway.py`
- Infra 实现：`memory_xxx_store.py` / `local_xxx.py`

### 代码规则
- 所有 I/O 必须 `async/await`
- 函数签名必须有类型注解
- `domain/` 内禁止出现 `import httpx`、`import sqlalchemy` 等外部库
- 新增 capability handler 放 `infra/worker/handlers/`，用 `@capability(name, desc)` 装饰

### 文件头注释格式
```python
"""
<层>/<模块>/<文件名>.py

<一句话说明职责>。
<补充说明（可选）>
"""
```

## 前端规范（React 19 + Ant Design）

### 文件放置
| 类型 | 目录 | 命名 |
|------|------|------|
| 页面组件 | `src/pages/` | `PascalCase.jsx` |
| 业务组件 | `src/components/` | `PascalCase.jsx` |
| API 客户端 | `src/utils/` | `camelCaseApi.js` |

### 代码规则
- 只用函数组件 + hooks，禁止 class 组件
- API 调用统一走 `src/utils/api.js` 的 `api` 或 `streamPost`，禁止裸 `fetch`
- SSE 流式输出用 `streamPost`，不用 EventSource
- Ant Design 组件优先，禁止引入其他 UI 库

## 测试规范

**后端：**
- 路径：`server/tests/<层路径>/test_<文件名>.py`
- 工具：`pytest` + `unittest.mock`
- 原则：禁止访问真实 LLM / 网络；`AsyncMock` 模拟 gateway

**前端：**
- 路径：`web/src/<同目录>/<组件>.test.jsx`
- 工具：`vitest` + `@testing-library/react`
- 原则：mock `graphApi` / `workerApi`，不发真实请求

## 每次代码改动后必须执行

**改动后立即执行，不可推迟到提交时。**

### 1. 补充或更新单测

每改动一个文件，对应测试文件同步更新：
- 新增逻辑 → 新增测试 case
- 修改逻辑 → 更新已有 case
- 删除逻辑 → 删除对应 case

case 覆盖三类：正常路径、边界条件、异常路径。

### 2. 运行后端测试

```bash
# 只跑受影响模块（快）
cd server && pytest tests/<对应路径>/test_xxx.py -v

# 改动范围较大时跑全量
cd server && pytest -v
```

测试不通过 → 修复后再继续，不跳过红测。

### 3. 运行前端测试

```bash
# 只跑受影响组件
cd web && npx vitest run src/<对应路径>/<组件>.test.jsx

# 全量
cd web && npx vitest run
```

### 4. 前端构建验证

有前端文件改动时：

```bash
cd web && npm run build
```

构建失败视同测试失败，必须修复。

---

## 新增功能检查清单

- [ ] 新 domain entity → 有对应 gateway 接口
- [ ] 新 infra 实现 → 实现了 gateway 抽象方法
- [ ] 新 adapter 路由 → 有对应 app service 方法
- [ ] 新 capability handler → 加了 `@capability` 装饰器
- [ ] 新前端组件 → API 调用走 utils/
- [ ] 所有改动 → 有对应测试 case 且测试通过
- [ ] 有前端改动 → `npm run build` 通过

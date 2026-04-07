"""
server/container.py

依赖注入容器：单例初始化 + FastAPI Depends 工厂函数。
所有跨层依赖在此装配，domain 层只持有抽象接口。

变更：
  - MemoryStore → JSON 文件 Store（持久化，重启不丢失）
  - LocalWorker → WorkerRouter（支持 Local + Remote Worker 聚合路由）
  - 新增 get_worker_router()（供 worker_ws.py 注册/注销远程 Worker）
"""

from server.app.agent.agent_app_service import AgentAppService
from server.app.agent.workspace_app_service import WorkspaceAppService
from server.app.worker.worker_app_service import WorkerAppService
from server.config import get_data_dir
from server.domain.agent.service.orchestrator import AgentOrchestrator
from server.infra.llm.llm_factory import LangChainLLMFactory
from server.infra.store.json_workspace_store import JsonWorkspaceStore
from server.infra.worker.local_worker import LocalWorker
from server.infra.worker.registry import scan_handlers
from server.infra.worker.worker_router import WorkerRouter

# ── 单例 ──────────────────────────────────────────────────────
_data_dir = get_data_dir()
_workspace_store = JsonWorkspaceStore(_data_dir)
_local_worker = LocalWorker()
_worker_router = WorkerRouter(_local_worker)
_llm_factory = LangChainLLMFactory()
# 无 Workspace 时的沙箱根目录：DATA_DIR/workspace/
_base_work_dir = str(_data_dir / "workspace")
_orchestrator = AgentOrchestrator(_worker_router, _llm_factory, _base_work_dir)
_agent_svc = AgentAppService(_orchestrator, _llm_factory, _workspace_store)
_workspace_svc = WorkspaceAppService(_workspace_store)
_worker_svc = WorkerAppService(_worker_router)


def init_container() -> None:
    """应用启动时调用：扫描并注册所有 @capability"""
    scan_handlers()


def get_agent_service() -> AgentAppService:
    return _agent_svc


def get_workspace_service() -> WorkspaceAppService:
    return _workspace_svc


def get_worker_service() -> WorkerAppService:
    return _worker_svc


def get_worker_router() -> WorkerRouter:
    """供 worker_ws.py 注册/注销远程 Worker"""
    return _worker_router

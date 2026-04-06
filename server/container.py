"""
server/container.py

依赖注入容器：单例初始化 + FastAPI Depends 工厂函数。
所有跨层依赖在此装配，domain 层只持有抽象接口。
"""

from server.app.agent.agent_app_service import AgentAppService
from server.app.worker.worker_app_service import WorkerAppService
from server.domain.agent.service.orchestrator import AgentOrchestrator
from server.infra.llm.llm_factory import LangChainLLMFactory
from server.infra.store.memory_agent_store import MemoryAgentStore
from server.infra.worker.local_worker import LocalWorker
from server.infra.worker.registry import scan_handlers

# ── 单例 ──────────────────────────────────────────────────────
_agent_store = MemoryAgentStore()
_local_worker = LocalWorker()
_llm_factory = LangChainLLMFactory()
_orchestrator = AgentOrchestrator(_local_worker, _llm_factory)
_agent_svc = AgentAppService(_agent_store, _orchestrator)
_worker_svc = WorkerAppService(_local_worker)


def init_container() -> None:
    """应用启动时调用：扫描并注册所有 @capability"""
    scan_handlers()


def get_agent_service() -> AgentAppService:
    return _agent_svc


def get_worker_service() -> WorkerAppService:
    return _worker_svc

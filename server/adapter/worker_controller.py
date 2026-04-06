"""
adapter/worker_controller.py

Worker capability 查询接入层。
路由前缀 /api/workers
"""

from fastapi import APIRouter, Depends

from server.app.worker.worker_app_service import WorkerAppService
from server.container import get_worker_service

router = APIRouter(prefix="/api/workers", tags=["Worker"])


@router.get("/capabilities")
def list_capabilities(svc: WorkerAppService = Depends(get_worker_service)):
    """列出所有已注册的内置 capability"""
    caps = svc.list_capabilities()
    return [
        {
            "name": c.name,
            "description": c.description,
            "worker_id": c.worker_id,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in c.parameters
            ],
        }
        for c in caps
    ]

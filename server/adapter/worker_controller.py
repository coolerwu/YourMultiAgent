"""
adapter/worker_controller.py

Worker capability 查询接入层。
路由前缀 /api/workers
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.app.worker.worker_app_service import WorkerAppService
from server.container import get_worker_service

router = APIRouter(prefix="/api/workers", tags=["Worker"])


class EnabledCapabilitiesReq(BaseModel):
    capability_names: list[str] = Field(default_factory=list)


@router.get("/capabilities")
def list_capabilities(svc: WorkerAppService = Depends(get_worker_service)):
    """列出所有当前可用且已授权的 capability"""
    caps = svc.list_capabilities()
    return [
        {
            "name": c.name,
            "description": c.description,
            "worker_id": c.worker_id,
            "category": c.category,
            "risk_level": c.risk_level,
            "requires_session": c.requires_session,
            "description_for_model": c.description_for_model,
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


@router.get("")
def list_workers(svc: WorkerAppService = Depends(get_worker_service)):
    workers = svc.list_workers()
    return [
        {
            "worker_id": worker.worker_id,
            "label": worker.label,
            "kind": worker.kind,
            "status": worker.status,
            "version": worker.version,
            "platform": worker.platform,
            "browser_type": worker.browser_type,
            "headless": worker.headless,
            "allowed_origins": worker.allowed_origins,
            "max_sessions": worker.max_sessions,
            "max_screenshot_bytes": worker.max_screenshot_bytes,
            "max_text_chars": worker.max_text_chars,
            "max_html_chars": worker.max_html_chars,
            "source": worker.source,
            "connected_at": worker.connected_at,
            "last_seen_at": worker.last_seen_at,
            "last_error": worker.last_error,
            "enabled_capability_names": worker.enabled_capability_names,
            "registered_capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "worker_id": cap.worker_id,
                    "category": cap.category,
                    "risk_level": cap.risk_level,
                    "requires_session": cap.requires_session,
                    "description_for_model": cap.description_for_model,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "description": p.description,
                            "required": p.required,
                            "default": p.default,
                        }
                        for p in cap.parameters
                    ],
                }
                for cap in worker.registered_capabilities
            ],
        }
        for worker in workers
    ]


@router.put("/{worker_id}/enabled-capabilities")
def update_enabled_capabilities(
    worker_id: str,
    req: EnabledCapabilitiesReq,
    svc: WorkerAppService = Depends(get_worker_service),
):
    try:
        worker = svc.set_enabled_capabilities(worker_id, req.capability_names)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "worker_id": worker.worker_id,
        "label": worker.label,
        "kind": worker.kind,
        "status": worker.status,
        "version": worker.version,
        "platform": worker.platform,
        "browser_type": worker.browser_type,
        "headless": worker.headless,
        "allowed_origins": worker.allowed_origins,
        "max_sessions": worker.max_sessions,
        "max_screenshot_bytes": worker.max_screenshot_bytes,
        "max_text_chars": worker.max_text_chars,
        "max_html_chars": worker.max_html_chars,
        "source": worker.source,
        "connected_at": worker.connected_at,
        "last_seen_at": worker.last_seen_at,
        "last_error": worker.last_error,
        "enabled_capability_names": worker.enabled_capability_names,
    }

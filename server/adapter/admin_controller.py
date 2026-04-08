"""
adapter/admin_controller.py

运维入口：
- POST /api/admin/update-now         启动增量更新
- GET  /api/admin/update-now/current 查询最近一次更新状态
"""

from fastapi import APIRouter, Depends

from server.app.settings.update_now_service import UpdateNowService
from server.container import get_update_now_service

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/update-now")
async def start_update_now(
    svc: UpdateNowService = Depends(get_update_now_service),
):
    return svc.start_update()


@router.get("/update-now/current")
async def get_current_update_now(
    svc: UpdateNowService = Depends(get_update_now_service),
):
    return svc.get_state()

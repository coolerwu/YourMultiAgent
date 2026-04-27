"""
server/main.py

FastAPI 应用入口：
- 注册路由（adapter 层）
- 托管前端静态文件（web/ 目录）
- 启动时初始化容器（扫描 @capability）
路由：
  agent_router      — /api/agents Prompt 优化
  agent_ws_router   — /ws/workspaces/{id}/run  WebSocket 执行
  worker_router     — /api/workers
  workspace_router  — /api/workspaces
  worker_ws_router  — /ws/worker  Remote Worker 接入
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.adapter.admin_controller import router as admin_router
from server.adapter.agent_controller import router as agent_router
from server.adapter.agent_ws import router as agent_ws_router
from server.adapter.auth_controller import router as auth_router
from server.adapter.settings_controller import router as settings_router
from server.adapter.worker_controller import router as worker_router
from server.adapter.worker_ws import router as worker_ws_router
from server.adapter.workspace_controller import router as workspace_router
from server.container import init_container
from server.support.page_auth import extract_bearer_token, load_auth_settings, verify_token
from server.support.app_logging import configure_app_logging, get_logger, install_http_logging_middleware, log_event

configure_app_logging()
logger = get_logger(__name__)

app = FastAPI(title="YourMultiAgent", version="0.1.0")
install_http_logging_middleware(app)

# ── CORS（开发阶段放开，生产按需收紧）──────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    settings = load_auth_settings()
    path = request.url.path
    if (
        settings.enabled
        and path.startswith("/api/")
        and path not in {"/api/health"}
        and not path.startswith("/api/auth/")
    ):
        token = extract_bearer_token(request.headers.get("authorization", ""))
        if not verify_token(token):
            return JSONResponse({"detail": "未登录或登录已过期"}, status_code=401)
    return await call_next(request)

# ── API 路由 ──────────────────────────────────────────────────
app.include_router(agent_router)
app.include_router(agent_ws_router)    # WebSocket: /ws/workspaces/{id}/run
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(worker_router)
app.include_router(workspace_router)
app.include_router(worker_ws_router)   # WebSocket: /ws/worker


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── 静态文件托管（前端编译产物）─────────────────────────────────
_WEB_DIR = Path(__file__).parent / "web"
if _WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")


# ── 启动事件 ──────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    log_event(logger, event="app_startup", layer="app", action="startup", status="started")
    init_container()
    log_event(logger, event="app_startup", layer="app", action="startup", status="success")


@app.on_event("shutdown")
def on_shutdown():
    log_event(logger, event="app_shutdown", layer="app", action="shutdown", status="success")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8080, reload=True, access_log=True, log_config=None)

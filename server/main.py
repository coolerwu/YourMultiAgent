"""
server/main.py

FastAPI 应用入口：
- 注册路由（adapter 层）
- 托管前端静态文件（web/ 目录）
- 启动时初始化容器（扫描 @capability）
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.adapter.agent_controller import router as agent_router
from server.adapter.worker_controller import router as worker_router
from server.container import init_container

app = FastAPI(title="YourMultiAgent", version="0.1.0")

# ── CORS（开发阶段放开，生产按需收紧）──────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 路由 ──────────────────────────────────────────────────
app.include_router(agent_router)
app.include_router(worker_router)


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
    init_container()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8080, reload=True)

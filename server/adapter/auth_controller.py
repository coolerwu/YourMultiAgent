"""
adapter/auth_controller.py

页面 AK/SK 登录接口。
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from server.support.page_auth import extract_bearer_token, load_auth_settings, login_with_aksk, verify_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginReq(BaseModel):
    access_key: str
    secret_key: str


@router.get("/status")
async def auth_status(request: Request) -> dict:
    settings = load_auth_settings()
    token = extract_bearer_token(request.headers.get("authorization", ""))
    return {"enabled": settings.enabled, "authenticated": bool(settings.enabled and verify_token(token))}


@router.post("/login")
async def login(req: LoginReq) -> dict:
    try:
        return login_with_aksk(req.access_key, req.secret_key)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

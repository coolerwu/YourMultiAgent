"""
infra/worker/handlers/http_tool.py

内置 HTTP capability：
- http_get   发起 GET 请求，返回响应文本
"""

import json as _json
from typing import Optional

import httpx

from server.infra.worker.registry import capability


@capability("http_get", "发起 HTTP GET 请求，返回响应内容（文本或 JSON）")
async def http_get(url: str, headers: Optional[str] = None) -> dict:
    """
    url     — 目标 URL
    headers — JSON 字符串格式的请求头，如 '{"Authorization": "Bearer xxx"}'
    """
    parsed_headers = {}
    if headers:
        try:
            parsed_headers = _json.loads(headers)
        except _json.JSONDecodeError:
            return {"error": "headers 格式错误，需为合法 JSON 字符串"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=parsed_headers)
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return {
                "status_code": resp.status_code,
                "body": body,
            }
    except httpx.TimeoutException:
        return {"error": "请求超时（15s）"}
    except Exception as e:
        return {"error": str(e)}

"""
app/settings/app_log_service.py

系统日志应用服务：读取当前唯一的 app.log 内容，供设置页展示。
"""

from __future__ import annotations

from pathlib import Path

from server.support.app_logging import get_app_log_path


class AppLogService:
    def __init__(self, log_path: str | None = None) -> None:
        self._log_path = Path(log_path).expanduser().resolve() if log_path else get_app_log_path()

    def get_app_log(self, lines: int = 300) -> dict:
        safe_lines = min(max(int(lines or 300), 1), 2000)
        path = self._log_path
        if not path.exists():
            return {
                "filename": path.name,
                "path": str(path),
                "content": "",
                "line_count": 0,
                "lines_requested": safe_lines,
                "exists": False,
                "updated_at": "",
            }

        content = path.read_text(encoding="utf-8", errors="replace")
        all_lines = content.splitlines()
        visible_lines = all_lines[-safe_lines:]
        return {
            "filename": path.name,
            "path": str(path),
            "content": "\n".join(visible_lines),
            "line_count": len(all_lines),
            "lines_requested": safe_lines,
            "exists": True,
            "updated_at": str(int(path.stat().st_mtime)),
        }

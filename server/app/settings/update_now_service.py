"""
server/app/settings/update_now_service.py

增量更新服务：
- 提供 Update Now 当前状态查询
- 在后台线程内执行 git pull + 依赖同步
- 通过状态文件跨进程重启保留最近一次结果
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class UpdateStep:
    name: str
    status: str = "pending"
    summary: str = ""


@dataclass
class UpdateNowState:
    status: str = "idle"
    started_at: str = ""
    finished_at: str = ""
    target_commit_before: str = ""
    target_commit_after: str = ""
    steps: list[UpdateStep] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    error: str = ""


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class UpdateNowService:
    def __init__(
        self,
        repo_dir: str,
        state_file: str,
        restart_callback: Callable[[], None] | None = None,
        command_runner: Callable[[list[str], str], subprocess.CompletedProcess[str]] | None = None,
    ):
        self._repo_dir = Path(repo_dir).resolve()
        self._state_file = Path(state_file).resolve()
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._restart_callback = restart_callback or self._default_restart
        self._command_runner = command_runner or self._run_command
        self._lock = threading.Lock()
        self._state = self._load_state()
        self._resume_from_previous_process()

    def get_state(self) -> dict:
        with self._lock:
            return self._serialize(self._state)

    def start_update(self) -> dict:
        with self._lock:
            if self._state.status in {"running", "restarting"}:
                return self._serialize(self._state)

            self._state = UpdateNowState(
                status="running",
                started_at=_utc_now(),
                steps=[
                    UpdateStep(name="inspect_repo"),
                    UpdateStep(name="git_fetch"),
                    UpdateStep(name="git_pull"),
                    UpdateStep(name="ensure_run_script"),
                    UpdateStep(name="upgrade_pip"),
                    UpdateStep(name="install_runtime"),
                    UpdateStep(name="restart_service"),
                ],
                logs=["开始执行 Update Now"],
            )
            self._save_state_locked()

        thread = threading.Thread(target=self._run_update, daemon=True)
        thread.start()
        return self.get_state()

    def _resume_from_previous_process(self) -> None:
        if self._state.status == "restarting":
            current_head = self._read_head()
            with self._lock:
                self._mark_success_locked("服务重启完成", current_head)
        elif self._state.status == "running":
            with self._lock:
                self._state.status = "failed"
                self._state.finished_at = _utc_now()
                self._state.error = self._state.error or "更新在服务重启前中断"
                self._state.logs.append("更新在服务重启前中断")
                self._save_state_locked()

    def _run_update(self) -> None:
        try:
            self._run_step("inspect_repo", self._inspect_repo)
            self._run_step("git_fetch", lambda: self._command_runner(["git", "fetch", "--all", "--prune"], str(self._repo_dir)))
            self._run_step("git_pull", lambda: self._command_runner(["git", "pull", "--ff-only"], str(self._repo_dir)))
            current_head = self._read_head()
            with self._lock:
                self._state.target_commit_after = current_head
                self._save_state_locked()
            self._run_step("ensure_run_script", self._ensure_run_script)
            self._run_step("upgrade_pip", self._upgrade_pip)
            self._run_step("install_runtime", self._install_runtime)

            with self._lock:
                self._set_step_status_locked("restart_service", "running", "准备重启服务进程")
                self._state.status = "restarting"
                self._state.finished_at = _utc_now()
                self._state.logs.append("更新完成，准备重启服务进程")
                self._save_state_locked()

            self._restart_callback()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._mark_failed_locked(str(exc))

    def _run_step(self, step_name: str, fn: Callable[[], subprocess.CompletedProcess[str] | str | None]) -> None:
        with self._lock:
            self._set_step_status_locked(step_name, "running", "")
            self._save_state_locked()

        result = fn()
        summary = self._summarize_result(result)

        with self._lock:
            self._set_step_status_locked(step_name, "success", summary)
            if summary:
                self._state.logs.append(f"{step_name}: {summary}")
            self._save_state_locked()

    def _inspect_repo(self) -> str:
        before = self._read_head()
        with self._lock:
            self._state.target_commit_before = before
            self._save_state_locked()
        return before

    def _ensure_run_script(self) -> str:
        run_path = self._repo_dir / "run.sh"
        run_path.chmod(run_path.stat().st_mode | 0o111)
        return "run.sh 已确保可执行"

    def _upgrade_pip(self) -> subprocess.CompletedProcess[str]:
        pip_bin = str(self._repo_dir / ".venv" / "bin" / "pip")
        return self._command_runner([pip_bin, "install", "--upgrade", "pip"], str(self._repo_dir))

    def _install_runtime(self) -> subprocess.CompletedProcess[str]:
        pip_bin = str(self._repo_dir / ".venv" / "bin" / "pip")
        return self._command_runner(
            [pip_bin, "install", "--no-cache-dir", "-e", ".", "langgraph", "setuptools", "wheel"],
            str(self._repo_dir),
        )

    def _read_head(self) -> str:
        result = self._command_runner(["git", "rev-parse", "HEAD"], str(self._repo_dir))
        return result.stdout.strip()

    def _run_command(self, cmd: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        output = "\n".join(part.strip() for part in [result.stdout, result.stderr] if part and part.strip()).strip()
        if output:
            with self._lock:
                self._state.logs.append(output)
                self._save_state_locked()
        if result.returncode != 0:
            raise RuntimeError(output or f"命令执行失败: {' '.join(cmd)}")
        return result

    def _default_restart(self) -> None:
        def _exit_process() -> None:
            time.sleep(0.3)
            os._exit(0)

        threading.Thread(target=_exit_process, daemon=True).start()

    def _set_step_status_locked(self, step_name: str, status: str, summary: str) -> None:
        for step in self._state.steps:
            if step.name == step_name:
                step.status = status
                step.summary = summary
                return

    def _mark_success_locked(self, message: str, current_head: str) -> None:
        self._state.status = "success"
        self._state.finished_at = _utc_now()
        self._state.target_commit_after = current_head
        self._set_step_status_locked("restart_service", "success", message)
        self._state.logs.append(message)
        self._save_state_locked()

    def _mark_failed_locked(self, error: str) -> None:
        self._state.status = "failed"
        self._state.finished_at = _utc_now()
        self._state.error = error
        self._state.logs.append(error)
        for step in self._state.steps:
            if step.status == "running":
                step.status = "failed"
                step.summary = error
                break
        self._save_state_locked()

    def _serialize(self, state: UpdateNowState) -> dict:
        return {
            "status": state.status,
            "started_at": state.started_at,
            "finished_at": state.finished_at,
            "target_commit_before": state.target_commit_before,
            "target_commit_after": state.target_commit_after,
            "steps": [asdict(step) for step in state.steps],
            "logs": list(state.logs),
            "error": state.error,
        }

    def _load_state(self) -> UpdateNowState:
        if not self._state_file.exists():
            return UpdateNowState()
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UpdateNowState()
        return UpdateNowState(
            status=raw.get("status", "idle"),
            started_at=raw.get("started_at", ""),
            finished_at=raw.get("finished_at", ""),
            target_commit_before=raw.get("target_commit_before", ""),
            target_commit_after=raw.get("target_commit_after", ""),
            steps=[UpdateStep(**item) for item in raw.get("steps", [])],
            logs=list(raw.get("logs", [])),
            error=raw.get("error", ""),
        )

    def _save_state_locked(self) -> None:
        self._state_file.write_text(
            json.dumps(self._serialize(self._state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _summarize_result(self, result: subprocess.CompletedProcess[str] | str | None) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        lines = [
            line.strip()
            for line in f"{result.stdout}\n{result.stderr}".splitlines()
            if line.strip()
        ]
        return lines[-1] if lines else "ok"

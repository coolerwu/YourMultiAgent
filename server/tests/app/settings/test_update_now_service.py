import subprocess
import time

from server.app.settings.update_now_service import UpdateNowService


def _completed(cmd: list[str], stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)


def test_start_update_runs_steps_and_marks_restarting(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    run_sh = repo_dir / "run.sh"
    run_sh.write_text("#!/bin/bash\n", encoding="utf-8")
    state_file = tmp_path / "state" / "update_now.json"
    restart_called = {"value": False}
    calls: list[list[str]] = []

    def fake_runner(cmd: list[str], _cwd: str):
        calls.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "HEAD"]:
            if len([item for item in calls if item[:3] == ["git", "rev-parse", "HEAD"]]) == 1:
                return _completed(cmd, stdout="oldsha\n")
            return _completed(cmd, stdout="newsha\n")
        return _completed(cmd, stdout="ok\n")

    svc = UpdateNowService(
        repo_dir=str(repo_dir),
        state_file=str(state_file),
        restart_callback=lambda: restart_called.__setitem__("value", True),
        command_runner=fake_runner,
    )

    state = svc.start_update()

    assert state["status"] == "running"

    for _ in range(200):
        current = svc.get_state()
        if current["status"] == "restarting":
            break
        time.sleep(0.01)
    else:
        raise AssertionError("更新任务未进入 restarting")

    assert restart_called["value"] is True
    assert current["target_commit_before"] == "oldsha"
    assert current["target_commit_after"] == "newsha"
    assert any(step["name"] == "restart_service" and step["status"] == "running" for step in current["steps"])
    assert any(cmd[:3] == ["git", "fetch", "--all"] for cmd in calls)
    assert any(cmd[:3] == ["git", "pull", "--ff-only"] for cmd in calls)


def test_resume_from_restarting_marks_success(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "run.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    state_file = tmp_path / "state" / "update_now.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        """
        {
          "status": "restarting",
          "started_at": "2026-04-08T00:00:00Z",
          "steps": [
            {"name": "restart_service", "status": "running", "summary": ""}
          ],
          "logs": ["更新完成，准备重启服务进程"]
        }
        """,
        encoding="utf-8",
    )

    def fake_runner(cmd: list[str], _cwd: str):
        if cmd[:3] == ["git", "rev-parse", "HEAD"]:
            return _completed(cmd, stdout="aftersha\n")
        return _completed(cmd, stdout="ok\n")

    svc = UpdateNowService(
        repo_dir=str(repo_dir),
        state_file=str(state_file),
        restart_callback=lambda: None,
        command_runner=fake_runner,
    )

    current = svc.get_state()

    assert current["status"] == "success"
    assert current["target_commit_after"] == "aftersha"
    assert current["steps"][0]["status"] == "success"

from pathlib import Path

from server.infra.codex import codex_cli


def test_build_install_command_uses_user_prefix(monkeypatch):
    monkeypatch.setattr(codex_cli, "os_family", lambda: "linux")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/qiuqiu"))

    assert codex_cli.build_install_command() == [
        "npm",
        "install",
        "-g",
        "@openai/codex",
        "--prefix",
        "/home/qiuqiu/.local",
    ]

    assert codex_cli.build_install_manual_command() == "npm install -g @openai/codex --prefix /home/qiuqiu/.local"


def test_detect_codex_path_falls_back_to_user_bin(monkeypatch):
    monkeypatch.setattr(codex_cli, "os_family", lambda: "linux")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/qiuqiu"))
    monkeypatch.setattr(codex_cli.shutil, "which", lambda _name: "")
    monkeypatch.setattr(codex_cli.os.path, "exists", lambda path: path == "/home/qiuqiu/.local/bin/codex")
    monkeypatch.setattr(codex_cli.os, "access", lambda path, _mode: path == "/home/qiuqiu/.local/bin/codex")

    assert codex_cli.detect_codex_path() == "/home/qiuqiu/.local/bin/codex"

"""
tests/infra/worker/test_git_tool.py

Git capability 单测：覆盖 Git 命令执行、路径安全、错误处理。
"""

import subprocess

import pytest

from server.infra.worker.handlers.git_tool import (
    git_add,
    git_branch,
    git_checkout,
    git_clone,
    git_commit,
    git_diff,
    git_log,
    git_pull,
    git_status,
)


@pytest.mark.asyncio
async def test_git_status_in_non_git_directory(tmp_path):
    """在非 Git 目录执行 status 应返回错误"""
    result = await git_status(_context={"work_dir": str(tmp_path)})

    assert "error" in result
    assert result.get("is_git_repo") is False


@pytest.mark.asyncio
async def test_git_status_in_git_repository(tmp_path):
    """在 Git 仓库执行 status 应返回成功"""
    # 初始化 Git 仓库
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    result = await git_status(_context={"work_dir": str(tmp_path)})

    assert "error" not in result or result.get("returncode") == 0
    assert "returncode" in result


@pytest.mark.asyncio
async def test_git_log_in_repository(tmp_path):
    """在 Git 仓库执行 log"""
    # 初始化 Git 仓库并创建提交
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    # 创建文件并提交
    (tmp_path / "test.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True, check=True)

    result = await git_log(max_count=5, _context={"work_dir": str(tmp_path)})

    assert result["returncode"] == 0
    assert "initial" in result["stdout"]


@pytest.mark.asyncio
async def test_git_branch_operations(tmp_path):
    """测试分支操作"""
    # 初始化 Git 仓库并创建提交
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    (tmp_path / "test.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True, check=True)

    # 测试列出分支
    result = await git_branch(list_branches=True, _context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0
    assert "main" in result["stdout"] or "master" in result["stdout"]

    # 测试创建分支
    result = await git_branch(create="feature/test", _context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0

    # 验证分支创建成功
    result = await git_branch(list_branches=True, _context={"work_dir": str(tmp_path)})
    assert "feature/test" in result["stdout"]


@pytest.mark.asyncio
async def test_git_checkout_branch(tmp_path):
    """测试切换分支"""
    # 初始化 Git 仓库并创建提交
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    (tmp_path / "test.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True, check=True)

    # 创建并切换到新分支
    result = await git_checkout(branch="feature/new", create=True, _context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0

    # 验证当前分支
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(tmp_path), capture_output=True, text=True)
    assert "feature/new" in result.stdout


@pytest.mark.asyncio
async def test_git_add_path_security(tmp_path):
    """测试 git_add 路径安全"""
    # 初始化 Git 仓库
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)

    # 创建嵌套目录结构
    work_dir = tmp_path / "agent"
    work_dir.mkdir()
    (work_dir / "file.txt").write_text("content")

    # 允许添加 work_dir 内的文件
    result = await git_add(path="file.txt", _context={"work_dir": str(work_dir)})
    assert result["returncode"] == 0

    # 阻止添加 work_dir 外的文件
    result = await git_add(path="../outside.txt", _context={"work_dir": str(work_dir)})
    assert "error" in result
    assert "不在允许范围" in result["error"]


@pytest.mark.asyncio
async def test_git_add_all_files(tmp_path):
    """测试 git_add -A"""
    # 初始化 Git 仓库
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)

    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")

    result = await git_add(all_files=True, _context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0

    # 验证已暂存
    result = subprocess.run(["git", "status", "--porcelain"], cwd=str(tmp_path), capture_output=True, text=True)
    assert "A  file1.txt" in result.stdout
    assert "A  file2.txt" in result.stdout


@pytest.mark.asyncio
async def test_git_commit(tmp_path):
    """测试 git commit"""
    # 初始化 Git 仓库
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    (tmp_path / "file.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)

    result = await git_commit(message="Test commit", _context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0

    # 验证提交
    result = subprocess.run(["git", "log", "-1", "--oneline"], cwd=str(tmp_path), capture_output=True, text=True)
    assert "Test commit" in result.stdout


@pytest.mark.asyncio
async def test_git_commit_empty_message_without_amend():
    """测试空提交信息且非 amend 时应返回错误"""
    result = await git_commit(message="")
    assert "error" in result
    assert "提交信息不能为空" in result["error"]


@pytest.mark.asyncio
async def test_git_diff(tmp_path):
    """测试 git diff"""
    # 初始化 Git 仓库
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    (tmp_path / "file.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True, check=True)

    # 修改文件
    (tmp_path / "file.txt").write_text("modified")

    result = await git_diff(_context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0
    assert "modified" in result["stdout"]


@pytest.mark.asyncio
async def test_git_diff_cached(tmp_path):
    """测试 git diff --cached"""
    # 初始化 Git 仓库
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

    (tmp_path / "file.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)

    result = await git_diff(cached=True, _context={"work_dir": str(tmp_path)})
    assert result["returncode"] == 0
    assert "content" in result["stdout"]


@pytest.mark.asyncio
async def test_git_clone(tmp_path):
    """测试 git clone"""
    # 先创建一个源仓库
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init"], cwd=str(source), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(source), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(source), capture_output=True)
    (source / "file.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=str(source), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(source), capture_output=True, check=True)

    # 克隆到目标目录
    target_parent = tmp_path / "parent"
    target_parent.mkdir()

    result = await git_clone(
        repository=str(source),
        directory="cloned",
        _context={"work_dir": str(target_parent)}
    )
    assert result["returncode"] == 0

    # 验证克隆成功
    cloned_dir = target_parent / "cloned"
    assert cloned_dir.exists()
    assert (cloned_dir / ".git").exists()
    assert (cloned_dir / "file.txt").read_text() == "content"


@pytest.mark.asyncio
async def test_git_pull(tmp_path):
    """测试 git pull"""
    # 创建远程仓库
    remote = tmp_path / "remote"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=str(remote), capture_output=True, check=True)

    # 创建本地仓库并推送初始提交
    local = tmp_path / "local"
    local.mkdir()
    subprocess.run(["git", "clone", str(remote), str(local)], capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(local), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(local), capture_output=True)

    (local / "file.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=str(local), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(local), capture_output=True, check=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=str(local), capture_output=True, check=True)

    # 创建另一个克隆并添加新提交
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(remote), str(other)], capture_output=True, check=True)
    (other / "new.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=str(other), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "add new file"], cwd=str(other), capture_output=True, check=True)
    subprocess.run(["git", "push"], cwd=str(other), capture_output=True, check=True)

    # 在本地执行 pull
    result = await git_pull(_context={"work_dir": str(local)})
    assert result["returncode"] == 0

    # 验证新文件已拉取
    assert (local / "new.txt").exists()
    assert (local / "new.txt").read_text() == "new content"

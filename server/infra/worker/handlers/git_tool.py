"""
infra/worker/handlers/git_tool.py

内置 Git capability：
- git_status      查看仓库状态
- git_log         查看提交历史
- git_clone       克隆仓库
- git_pull        拉取更新
- git_add         添加文件到暂存区
- git_commit      提交更改
- git_branch      列出或创建分支
- git_checkout    切换分支
- git_diff        查看变更差异
"""

import subprocess
from pathlib import Path
from typing import Any

from server.infra.worker.registry import capability


def _get_work_dir(context: dict[str, Any] | None) -> str:
    return context.get("work_dir", ".") if context else "."


def _run_git_command(
    args: list[str],
    cwd: str,
    timeout: int = 30,
    check: bool = False
) -> dict:
    """
    执行 Git 命令的通用函数。

    Args:
        args: Git 命令参数列表（不含 'git'）
        cwd: 工作目录
        timeout: 超时时间（秒）
        check: 是否检查返回码，非零时返回 error

    Returns:
        包含 stdout/stderr/returncode 的字典
    """
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        if check and result.returncode != 0:
            return {
                "error": f"Git 命令执行失败: {result.stderr}",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Git 命令执行超时（{timeout}s）"}
    except FileNotFoundError:
        return {"error": "Git 未安装或不在 PATH 中"}
    except Exception as e:
        return {"error": str(e)}


def _resolve_path(path: str, work_dir: str) -> Path:
    """解析路径，相对路径基于 work_dir"""
    p = Path(path)
    if not p.is_absolute():
        p = Path(work_dir).expanduser().resolve() / p
    return p.resolve()


@capability("git_status", "查看 Git 仓库状态（git status）")
async def git_status(
    short: bool = True,
    branch: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    查看 Git 仓库状态。

    Args:
        short: 使用简洁格式（默认 True）
        branch: 显示分支信息（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["status"]
    if short:
        args.append("-s")
    if branch:
        args.append("-b")

    result = _run_git_command(args, cwd)

    # 如果返回码非零，可能是非 Git 仓库，提供友好错误
    if result.get("returncode") != 0:
        stderr = result.get("stderr", "").lower()
        if "not a git repository" in stderr or "fatal: not a git" in stderr:
            return {"error": "当前目录不是 Git 仓库", "is_git_repo": False}

    return result


@capability("git_log", "查看 Git 提交历史（git log）")
async def git_log(
    max_count: int = 10,
    oneline: bool = True,
    graph: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    查看 Git 提交历史。

    Args:
        max_count: 最多显示多少条提交（默认 10）
        oneline: 使用一行格式显示（默认 True）
        graph: 显示分支图谱（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["log"]
    if max_count > 0:
        args.extend(["-n", str(max_count)])
    if oneline:
        args.append("--oneline")
    if graph:
        args.append("--graph")
    args.append("--decorate")

    return _run_git_command(args, cwd)


@capability("git_clone", "克隆 Git 仓库（git clone）")
async def git_clone(
    repository: str,
    directory: str = "",
    branch: str = "",
    depth: int = 0,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    克隆 Git 仓库到本地。

    Args:
        repository: 仓库 URL 或路径
        directory: 本地目录名（默认使用仓库名）
        branch: 指定克隆的分支
        depth: 浅克隆深度（0 表示完整克隆）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["clone"]
    if branch:
        args.extend(["-b", branch, "--single-branch"])
    if depth > 0:
        args.extend(["--depth", str(depth)])

    args.append(repository)
    if directory:
        args.append(directory)

    return _run_git_command(args, cwd, timeout=120)


@capability("git_pull", "从远程拉取更新（git pull）")
async def git_pull(
    remote: str = "origin",
    branch: str = "",
    rebase: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    从远程仓库拉取更新。

    Args:
        remote: 远程仓库名（默认 origin）
        branch: 分支名（默认当前分支跟踪的分支）
        rebase: 使用 rebase 而非 merge（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["pull"]
    if rebase:
        args.append("--rebase")
    if remote:
        args.append(remote)
    if branch:
        args.append(branch)

    return _run_git_command(args, cwd, timeout=60)


@capability("git_add", "添加文件到 Git 暂存区（git add）")
async def git_add(
    path: str = ".",
    all_files: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    添加文件到 Git 暂存区。

    Args:
        path: 要添加的文件或目录路径（默认 .）
        all_files: 添加所有修改（git add -A，默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    if all_files:
        return _run_git_command(["add", "-A"], cwd)

    # 解析路径，检查是否在 work_dir 内
    target = _resolve_path(path, cwd)
    try:
        target.relative_to(Path(cwd).resolve())
    except ValueError:
        return {"error": f"路径不在允许范围内: {path}"}

    return _run_git_command(["add", str(target)], cwd)


@capability("git_commit", "提交 Git 更改（git commit）")
async def git_commit(
    message: str,
    amend: bool = False,
    no_verify: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    提交暂存区的更改。

    Args:
        message: 提交信息
        amend: 修改上一次提交（默认 False）
        no_verify: 跳过 pre-commit hooks（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    if not message and not amend:
        return {"error": "提交信息不能为空（除非使用 amend）"}

    args = ["commit"]
    if message:
        args.extend(["-m", message])
    if amend:
        args.append("--amend")
    if no_verify:
        args.append("--no-verify")

    return _run_git_command(args, cwd, check=True)


@capability("git_branch", "列出或创建 Git 分支（git branch）")
async def git_branch(
    create: str = "",
    delete: str = "",
    list_branches: bool = True,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    列出、创建或删除分支。

    Args:
        create: 创建新分支的名称
        delete: 删除分支的名称
        list_branches: 列出所有分支（默认 True）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    if create:
        return _run_git_command(["branch", create], cwd)
    if delete:
        return _run_git_command(["branch", "-d", delete], cwd)
    if list_branches:
        return _run_git_command(["branch", "-a"], cwd)

    return {"error": "请指定 create、delete 或 list_branches 之一"}


@capability("git_checkout", "切换 Git 分支（git checkout）")
async def git_checkout(
    branch: str,
    create: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    切换到指定分支。

    Args:
        branch: 分支名
        create: 如果分支不存在则创建（-b，默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)

    return _run_git_command(args, cwd)


@capability("git_diff", "查看 Git 变更差异（git diff）")
async def git_diff(
    cached: bool = False,
    path: str = "",
    _context: dict[str, Any] | None = None
) -> dict:
    """
    查看工作区与暂存区之间的差异。

    Args:
        cached: 查看暂存区与 HEAD 之间的差异（默认 False）
        path: 指定文件或目录路径
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["diff"]
    if cached:
        args.append("--cached")
    if path:
        target = _resolve_path(path, cwd)
        args.append(str(target))

    return _run_git_command(args, cwd)

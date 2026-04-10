"""
infra/worker/handlers/gh_tool.py

内置 GitHub CLI (gh) capability：
- gh_pr_create      创建 Pull Request
- gh_pr_list        列出 Pull Request
- gh_pr_view        查看 Pull Request 详情
- gh_repo_view      查看仓库信息
"""

import subprocess
from pathlib import Path
from typing import Any

from ..registry import capability


def _get_work_dir(context: dict[str, Any] | None) -> str:
    return context.get("work_dir", ".") if context else "."


def _run_gh_command(
    args: list[str],
    cwd: str,
    timeout: int = 60,
    check: bool = False
) -> dict:
    """
    执行 GitHub CLI 命令的通用函数。

    Args:
        args: gh 命令参数列表（不含 'gh'）
        cwd: 工作目录
        timeout: 超时时间（秒）
        check: 是否检查返回码，非零时返回 error

    Returns:
        包含 stdout/stderr/returncode 的字典
    """
    cmd = ["gh"] + args
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
                "error": f"gh 命令执行失败: {result.stderr}",
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
        return {"error": f"gh 命令执行超时（{timeout}s）"}
    except FileNotFoundError:
        return {"error": "GitHub CLI (gh) 未安装或不在 PATH 中"}
    except Exception as e:
        return {"error": str(e)}


@capability("gh_pr_create", "创建 GitHub Pull Request（gh pr create）")
async def gh_pr_create(
    title: str,
    body: str = "",
    base: str = "",
    head: str = "",
    draft: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    创建 GitHub Pull Request。

    Args:
        title: PR 标题
        body: PR 描述内容
        base: 目标分支（默认仓库默认分支）
        head: 源分支（默认当前分支）
        draft: 创建为草稿 PR（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    if not title:
        return {"error": "PR 标题不能为空"}

    args = ["pr", "create", "--title", title]

    if body:
        args.extend(["--body", body])
    if base:
        args.extend(["--base", base])
    if head:
        args.extend(["--head", head])
    if draft:
        args.append("--draft")

    return _run_gh_command(args, cwd, timeout=60, check=True)


@capability("gh_pr_list", "列出 GitHub Pull Requests（gh pr list）")
async def gh_pr_list(
    state: str = "open",
    limit: int = 30,
    author: str = "",
    base: str = "",
    _context: dict[str, Any] | None = None
) -> dict:
    """
    列出 GitHub Pull Requests。

    Args:
        state: PR 状态 - open/closed/merged/all（默认 open）
        limit: 最多显示数量（默认 30）
        author: 按作者筛选
        base: 按目标分支筛选
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["pr", "list", "--state", state, "--limit", str(limit)]

    if author:
        args.extend(["--author", author])
    if base:
        args.extend(["--base", base])

    return _run_gh_command(args, cwd)


@capability("gh_pr_view", "查看 GitHub Pull Request 详情（gh pr view）")
async def gh_pr_view(
    number: int = 0,
    branch: str = "",
    web: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    查看 GitHub Pull Request 详情。

    Args:
        number: PR 编号（与 branch 二选一）
        branch: 分支名（与 number 二选一）
        web: 在浏览器中打开（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["pr", "view"]

    if number:
        args.append(str(number))
    elif branch:
        args.append(branch)

    if web:
        args.append("--web")
    else:
        args.extend(["--comments", "--json", "number,title,state,body,author,headRefName,baseRefName,url,createdAt,updatedAt,mergeStateStatus,mergeable"])

    return _run_gh_command(args, cwd)


@capability("gh_repo_view", "查看 GitHub 仓库信息（gh repo view）")
async def gh_repo_view(
    repo: str = "",
    web: bool = False,
    _context: dict[str, Any] | None = None
) -> dict:
    """
    查看 GitHub 仓库信息。

    Args:
        repo: 仓库名（owner/repo 格式，默认当前仓库）
        web: 在浏览器中打开（默认 False）
    """
    context = _context or {}
    work_dir = _get_work_dir(context)
    cwd = str(Path(work_dir).expanduser().resolve())

    args = ["repo", "view"]

    if repo:
        args.append(repo)

    if web:
        args.append("--web")
    else:
        args.extend(["--json", "name,owner,description,defaultBranch,url,sshUrl,viewerPermission"])

    return _run_gh_command(args, cwd)

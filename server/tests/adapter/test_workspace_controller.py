"""
tests/adapter/test_workspace_controller.py

Workspace 控制器测试：覆盖 Git 仓库验证端点。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from server.adapter.workspace_controller import AgentNodeReq, _agent_node_cmd, verify_git_repository
from server.domain.agent.agent_entity import LLMProvider


def test_agent_node_cmd_maps_git_workflow():
    req = AgentNodeReq(
        id="coordinator",
        name="主控",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="你是主控",
        git_workflow={
            "enabled": True,
            "repoUrl": "https://github.com/test/repo.git",
            "baseBranch": "develop",
        },
    )

    cmd = _agent_node_cmd(req)

    assert cmd.git_workflow is not None
    assert cmd.git_workflow.enabled is True
    assert cmd.git_workflow.repoUrl == "https://github.com/test/repo.git"
    assert cmd.git_workflow.baseBranch == "develop"


@pytest.mark.asyncio
async def test_verify_git_repository_workspace_not_found():
    """Workspace 不存在时返回 404"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.side_effect = ValueError("Workspace 不存在")

    with pytest.raises(Exception) as exc_info:
        await verify_git_repository(
            workspace_id="test-ws",
            req=MagicMock(repo_url="https://github.com/test/repo.git"),
            svc=mock_svc,
        )
    assert "404" in str(exc_info.value) or "Workspace 不存在" in str(exc_info.value)


@pytest.mark.asyncio
async def test_verify_git_repository_empty_url():
    """空仓库地址返回 400"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.side_effect = ValueError("仓库地址不能为空")

    with pytest.raises(Exception) as exc_info:
        await verify_git_repository(
            workspace_id="test-ws",
            req=MagicMock(repo_url="   "),
            svc=mock_svc,
        )
    assert "400" in str(exc_info.value) or "仓库地址不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_verify_git_repository_local_valid():
    """本地 Git 仓库验证成功"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.return_value = {"valid": True, "message": "本地 Git 仓库有效", "type": "local"}
    result = await verify_git_repository(
        workspace_id="test-ws",
        req=MagicMock(repo_url="/path/to/repo"),
        svc=mock_svc,
    )

    assert result["valid"] is True
    assert result["type"] == "local"
    assert "有效" in result["message"]
    mock_svc.verify_git_repository.assert_awaited_once_with("test-ws", "/path/to/repo")


@pytest.mark.asyncio
async def test_verify_git_repository_local_invalid():
    """本地路径不是 Git 仓库"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.return_value = {
        "valid": False,
        "error": "本地路径不是有效的 Git 仓库（缺少 .git 目录）",
        "type": "local",
    }
    result = await verify_git_repository(
        workspace_id="test-ws",
        req=MagicMock(repo_url="/path/to/not-repo"),
        svc=mock_svc,
    )

    assert result["valid"] is False
    assert result["type"] == "local"
    assert "不是有效的 Git 仓库" in result["error"]


@pytest.mark.asyncio
async def test_verify_git_repository_remote_success():
    """远程 Git 仓库验证成功"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.return_value = {
        "valid": True,
        "message": "仓库地址可访问",
        "type": "remote",
        "branches": ["main", "feature/test"],
    }
    result = await verify_git_repository(
        workspace_id="test-ws",
        req=MagicMock(repo_url="https://github.com/test/repo.git"),
        svc=mock_svc,
    )

    assert result["valid"] is True
    assert result["type"] == "remote"
    assert "可访问" in result["message"]
    assert "branches" in result
    assert "main" in result["branches"]
    assert "feature/test" in result["branches"]


@pytest.mark.asyncio
async def test_verify_git_repository_remote_auth_failed():
    """远程仓库认证失败"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.return_value = {
        "valid": False,
        "error": "认证失败：需要用户名/密码或 SSH 密钥",
        "type": "remote",
    }
    result = await verify_git_repository(
        workspace_id="test-ws",
        req=MagicMock(repo_url="https://github.com/test/private.git"),
        svc=mock_svc,
    )

    assert result["valid"] is False
    assert result["type"] == "remote"
    assert "认证失败" in result["error"]


@pytest.mark.asyncio
async def test_verify_git_repository_remote_timeout():
    """远程仓库验证超时"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.return_value = {
        "valid": False,
        "error": "验证超时（30秒），请检查网络连接",
        "type": "remote",
    }
    result = await verify_git_repository(
        workspace_id="test-ws",
        req=MagicMock(repo_url="https://slow-git-server.com/repo.git"),
        svc=mock_svc,
    )

    assert result["valid"] is False
    assert result["type"] == "remote"
    assert "超时" in result["error"]


@pytest.mark.asyncio
async def test_verify_git_repository_remote_not_found():
    """远程仓库不存在"""
    mock_svc = AsyncMock()
    mock_svc.verify_git_repository.return_value = {
        "valid": False,
        "error": "仓库不存在，请检查 URL",
        "type": "remote",
    }
    result = await verify_git_repository(
        workspace_id="test-ws",
        req=MagicMock(repo_url="https://github.com/notfound/repo.git"),
        svc=mock_svc,
    )

    assert result["valid"] is False
    assert result["type"] == "remote"
    assert "不存在" in result["error"] or "not found" in result["error"]

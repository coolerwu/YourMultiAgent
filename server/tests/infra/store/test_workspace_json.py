"""
tests/infra/store/test_workspace_json.py

Workspace JSON 存储测试：覆盖 git_workflow 序列化和反序列化。
"""

import pytest
from pathlib import Path
import tempfile
import json

from server.infra.store.workspace_json import (
    _agent_from_dict,
    workspace_to_payload,
    workspace_from_payload,
    save_workspace_payload,
    load_workspace_payload,
)
from server.domain.agent.agent_entity import (
    AgentEntity,
    GitWorkflowConfig,
    LLMProvider,
    WorkspaceEntity,
    WorkspaceKind,
)


def test_agent_from_dict_without_git_workflow():
    """反序列化没有 git_workflow 的 agent"""
    data = {
        "id": "test",
        "name": "Test Agent",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "system_prompt": "You are a test agent.",
        "temperature": 0.7,
        "max_tokens": 4096,
        "tools": [],
    }
    agent = _agent_from_dict(data)
    assert agent.id == "test"
    assert agent.git_workflow is None


def test_agent_from_dict_with_git_workflow():
    """反序列化包含 git_workflow 的 agent"""
    data = {
        "id": "coordinator",
        "name": "Coordinator",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "system_prompt": "You are the coordinator.",
        "git_workflow": {
            "enabled": True,
            "repoUrl": "https://github.com/test/repo.git",
            "baseBranch": "main",
            "featureBranchPrefix": "feature/",
            "autoCreateBranch": True,
            "autoCommit": True,
            "commitMessageTemplate": "[Agent] {{task_name}}",
            "prTitleTemplate": "[Agent] {{task_name}}",
            "prBodyTemplate": "## Task\n{{task_description}}",
            "autoCreatePR": False,
            "requireReview": True,
        },
    }
    agent = _agent_from_dict(data)
    assert agent.git_workflow is not None
    assert agent.git_workflow.enabled is True
    assert agent.git_workflow.repoUrl == "https://github.com/test/repo.git"
    assert agent.git_workflow.baseBranch == "main"


def test_agent_from_dict_with_partial_git_workflow():
    """反序列化包含不完整 git_workflow 的 agent，使用默认值"""
    data = {
        "id": "coordinator",
        "name": "Coordinator",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "system_prompt": "You are the coordinator.",
        "git_workflow": {
            "enabled": True,
            "repoUrl": "https://github.com/test/repo.git",
            # 其他字段缺失
        },
    }
    agent = _agent_from_dict(data)
    assert agent.git_workflow is not None
    assert agent.git_workflow.enabled is True
    assert agent.git_workflow.repoUrl == "https://github.com/test/repo.git"
    # 使用默认值
    assert agent.git_workflow.baseBranch == "main"
    assert agent.git_workflow.autoCreateBranch is True


def test_workspace_roundtrip_with_git_workflow():
    """Workspace 完整序列化和反序列化循环"""
    coordinator = AgentEntity(
        id="coordinator",
        name="Coordinator",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="You are the coordinator.",
        git_workflow=GitWorkflowConfig(
            enabled=True,
            repoUrl="https://github.com/test/repo.git",
            baseBranch="develop",
        ),
    )
    worker = AgentEntity(
        id="worker1",
        name="Worker 1",
        provider=LLMProvider.OPENAI,
        model="gpt-4o",
        system_prompt="You are a worker.",
        # worker 没有 git_workflow
    )
    workspace = WorkspaceEntity(
        id="ws-test",
        name="Test Workspace",
        work_dir="/tmp/test",
        kind=WorkspaceKind.WORKSPACE,
        coordinator=coordinator,
        workers=[worker],
    )

    # 序列化
    payload = workspace_to_payload(workspace, [])

    # 验证序列化结果包含 git_workflow
    assert payload["coordinator"]["git_workflow"]["enabled"] is True
    assert payload["coordinator"]["git_workflow"]["repoUrl"] == "https://github.com/test/repo.git"

    # 反序列化
    restored = workspace_from_payload(payload)

    # 验证反序列化正确
    assert restored.coordinator.git_workflow is not None
    assert restored.coordinator.git_workflow.enabled is True
    assert restored.coordinator.git_workflow.repoUrl == "https://github.com/test/repo.git"
    assert restored.coordinator.git_workflow.baseBranch == "develop"
    # worker 没有 git_workflow
    assert restored.workers[0].git_workflow is None


def test_workspace_file_save_and_load():
    """Workspace 保存到文件并读取"""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "workspace.json"

        coordinator = AgentEntity(
            id="coordinator",
            name="Coordinator",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="You are the coordinator.",
            git_workflow=GitWorkflowConfig(
                enabled=True,
                repoUrl="https://github.com/test/repo.git",
            ),
        )
        workspace = WorkspaceEntity(
            id="ws-test",
            name="Test Workspace",
            work_dir="/tmp/test",
            coordinator=coordinator,
            workers=[],
        )

        # 保存
        payload = workspace_to_payload(workspace, [])
        save_workspace_payload(filepath, payload)

        # 读取
        loaded_payload = load_workspace_payload(filepath)
        restored = workspace_from_payload(loaded_payload)

        # 验证
        assert restored.coordinator.git_workflow is not None
        assert restored.coordinator.git_workflow.enabled is True
        assert restored.coordinator.git_workflow.repoUrl == "https://github.com/test/repo.git"

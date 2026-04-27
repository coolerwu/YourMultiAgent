"""
tests/domain/agent/test_agent_entity.py

Agent 实体测试：覆盖 GitWorkflowConfig 和 AgentEntity。
"""

import pytest

from server.domain.agent.agent_entity import (
    AgentEntity,
    GitWorkflowConfig,
    LLMProvider,
)


def test_git_workflow_config_defaults():
    """GitWorkflowConfig 默认值正确"""
    config = GitWorkflowConfig()
    assert config.enabled is False
    assert config.repoUrl == ""
    assert config.baseBranch == "main"
    assert config.featureBranchPrefix == "feature/"
    assert config.autoCreateBranch is True
    assert config.autoCommit is True
    assert config.commitMessageTemplate == "[Agent] {{task_name}}"
    assert config.prTitleTemplate == "[Agent] {{task_name}}"
    assert "{{task_description}}" in config.prBodyTemplate
    assert config.autoCreatePR is False
    assert config.requireReview is True


def test_git_workflow_config_custom():
    """GitWorkflowConfig 支持自定义值"""
    config = GitWorkflowConfig(
        enabled=True,
        repoUrl="https://github.com/test/repo.git",
        baseBranch="master",
        featureBranchPrefix="feat/",
        autoCreateBranch=False,
        autoCommit=False,
        autoCreatePR=True,
        requireReview=False,
    )
    assert config.enabled is True
    assert config.repoUrl == "https://github.com/test/repo.git"
    assert config.baseBranch == "master"
    assert config.featureBranchPrefix == "feat/"
    assert config.autoCreateBranch is False
    assert config.autoCommit is False
    assert config.autoCreatePR is True
    assert config.requireReview is False


def test_agent_entity_without_git_workflow():
    """AgentEntity 可以不设置 git_workflow"""
    agent = AgentEntity(
        id="test",
        name="Test Agent",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="You are a test agent.",
    )
    assert agent.git_workflow is None


def test_agent_entity_with_git_workflow():
    """AgentEntity 可以设置 git_workflow"""
    config = GitWorkflowConfig(enabled=True, repoUrl="https://github.com/test/repo.git")
    agent = AgentEntity(
        id="coordinator",
        name="Coordinator",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="You are the coordinator.",
        git_workflow=config,
    )
    assert agent.git_workflow is not None
    assert agent.git_workflow.enabled is True
    assert agent.git_workflow.repoUrl == "https://github.com/test/repo.git"


def test_agent_entity_resolved_work_subdir():
    """resolved_work_subdir 方法正确工作"""
    agent = AgentEntity(
        id="test",
        name="Test Agent",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="You are a test agent.",
        work_subdir="custom_dir",
    )
    assert agent.resolved_work_subdir() == "custom_dir"


def test_agent_entity_resolved_work_subdir_fallback():
    """resolved_work_subdir 在未设置时回退到 name"""
    agent = AgentEntity(
        id="test",
        name="Test Agent",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="You are a test agent.",
        work_subdir="",
    )
    assert agent.resolved_work_subdir() == "Test Agent"

"""
tests/infra/worker/test_system_handlers.py

system handlers 单测：共享目录读写规则。
"""

import pytest

from server.infra.worker.handlers.system import list_dir, read_file, write_file


@pytest.mark.asyncio
async def test_write_file_allows_workspace_shared_path(tmp_path):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    result = await write_file(
        "shared/PRD.md",
        "# PRD",
        _context={
            "work_dir": str(product_dir),
            "workspace_root": str(tmp_path),
        },
    )

    assert result["success"] is True
    assert result["path"] == str((tmp_path / "shared" / "PRD.md").resolve())
    assert (tmp_path / "shared" / "PRD.md").read_text(encoding="utf-8") == "# PRD"


@pytest.mark.asyncio
async def test_write_file_blocks_other_parent_paths(tmp_path):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    result = await write_file(
        "../other/secret.txt",
        "x",
        _context={
            "work_dir": str(product_dir),
            "workspace_root": str(tmp_path),
        },
    )

    assert result["success"] is False
    assert "workspace/shared" in result["error"]


@pytest.mark.asyncio
async def test_read_and_list_shared_path_resolve_to_workspace_root(tmp_path):
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    (shared_dir / "spec.md").write_text("hello", encoding="utf-8")
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    listed = await list_dir("shared", _context={"work_dir": str(product_dir), "workspace_root": str(tmp_path)})
    read = await read_file("shared/spec.md", _context={"work_dir": str(product_dir), "workspace_root": str(tmp_path)})

    assert listed["path"] == str(shared_dir.resolve())
    assert listed["entries"][0]["name"] == "spec.md"
    assert read["content"] == "hello"

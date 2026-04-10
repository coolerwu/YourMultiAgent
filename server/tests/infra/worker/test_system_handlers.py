"""
tests/infra/worker/test_system_handlers.py

system handlers 单测：共享目录读写规则。
"""

import pytest

from server.infra.worker.handlers.system import delete_dir, delete_file, list_dir, read_file, write_file


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


@pytest.mark.asyncio
async def test_delete_file_success(tmp_path):
    """测试删除文件成功"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    test_file = work_dir / "test.txt"
    test_file.write_text("content", encoding="utf-8")

    result = await delete_file("test.txt", _context={"work_dir": str(work_dir)})

    assert result["success"] is True
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_delete_file_not_exists(tmp_path):
    """测试删除不存在的文件"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    result = await delete_file("not_exists.txt", _context={"work_dir": str(work_dir)})

    assert result["success"] is False
    assert "文件不存在" in result["error"]


@pytest.mark.asyncio
async def test_delete_file_is_directory(tmp_path):
    """测试删除目录（传入文件删除函数）"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    test_dir = work_dir / "test_dir"
    test_dir.mkdir()

    result = await delete_file("test_dir", _context={"work_dir": str(work_dir)})

    assert result["success"] is False
    assert "不是文件" in result["error"]


@pytest.mark.asyncio
async def test_delete_file_blocks_parent_paths(tmp_path):
    """测试删除文件阻止访问父目录"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    result = await delete_file("../secret.txt", _context={"work_dir": str(work_dir)})

    assert result["success"] is False
    assert "work_dir" in result["error"] or "workspace/shared" in result["error"]
    assert outside_file.exists()  # 文件不应被删除


@pytest.mark.asyncio
async def test_delete_dir_empty(tmp_path):
    """测试删除空目录"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    test_dir = work_dir / "empty_dir"
    test_dir.mkdir()

    result = await delete_dir("empty_dir", _context={"work_dir": str(work_dir)})

    assert result["success"] is True
    assert not test_dir.exists()


@pytest.mark.asyncio
async def test_delete_dir_not_empty_without_recursive(tmp_path):
    """测试删除非空目录（不使用 recursive）"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    test_dir = work_dir / "non_empty"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    result = await delete_dir("non_empty", recursive=False, _context={"work_dir": str(work_dir)})

    assert result["success"] is False
    assert test_dir.exists()  # 目录不应被删除


@pytest.mark.asyncio
async def test_delete_dir_recursive(tmp_path):
    """测试递归删除非空目录"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    test_dir = work_dir / "nested"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")
    (test_dir / "subdir").mkdir()
    (test_dir / "subdir" / "another.txt").write_text("more content")

    result = await delete_dir("nested", recursive=True, _context={"work_dir": str(work_dir)})

    assert result["success"] is True
    assert not test_dir.exists()


@pytest.mark.asyncio
async def test_delete_dir_blocks_parent_paths(tmp_path):
    """测试删除目录阻止访问父目录"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    result = await delete_dir("../outside", _context={"work_dir": str(work_dir)})

    assert result["success"] is False
    assert outside_dir.exists()  # 目录不应被删除


@pytest.mark.asyncio
async def test_delete_dir_in_shared_path(tmp_path):
    """测试删除 shared 目录中的目录"""
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    test_dir = shared_dir / "test_folder"
    test_dir.mkdir()

    result = await delete_dir("shared/test_folder", _context={"work_dir": str(tmp_path / "work"), "workspace_root": str(tmp_path)})

    assert result["success"] is True
    assert not test_dir.exists()

#!/usr/bin/env python3
"""
提交前检查脚本：
1. 输出 git diff（staged + unstaged）供 Claude review
2. 列出缺少单测的模块
3. 检查 CLAUDE.md 大小，超过阈值时提示拆分
"""

import subprocess
import sys
import os
from pathlib import Path

CLAUDE_MD_SPLIT_THRESHOLD = 200  # 行数超过此值提示拆分

def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_diff() -> str:
    staged = run("git diff --cached")
    unstaged = run("git diff")
    return f"=== STAGED ===\n{staged}\n\n=== UNSTAGED ===\n{unstaged}"

def get_changed_files() -> list[str]:
    output = run("git diff --name-only HEAD")
    cached = run("git diff --cached --name-only")
    files = set(output.splitlines() + cached.splitlines())
    return [f for f in files if f]

def find_missing_tests(changed_files: list[str]) -> list[str]:
    """找出有变更但缺少对应测试文件的模块"""
    missing = []
    for f in changed_files:
        p = Path(f)
        # Python: server/app/agent/agent_app_service.py → server/tests/app/agent/test_agent_app_service.py
        if p.suffix == ".py" and "test" not in p.name and "main" not in p.name:
            parts = list(p.parts)
            if parts and parts[0] == "server":
                test_path = Path("server/tests").joinpath(*parts[1:])
                test_path = test_path.with_name(f"test_{test_path.name}")
                if not test_path.exists():
                    missing.append(f"{f} → 缺少 {test_path}")
        # JS/JSX: web/src/components/Foo.jsx → web/src/components/Foo.test.jsx
        elif p.suffix in (".jsx", ".js", ".ts", ".tsx") and ".test." not in p.name:
            test_path = p.with_name(p.stem + ".test" + p.suffix)
            if not test_path.exists():
                missing.append(f"{f} → 缺少 {test_path}")
    return missing

def check_claude_md() -> list[str]:
    warnings = []
    root = Path(".")
    for md in root.rglob("CLAUDE.md"):
        lines = md.read_text(encoding="utf-8").splitlines()
        if len(lines) > CLAUDE_MD_SPLIT_THRESHOLD:
            warnings.append(
                f"{md} 共 {len(lines)} 行，超过 {CLAUDE_MD_SPLIT_THRESHOLD} 行阈值，"
                f"建议将大段内容拆分到 docs/ 目录并用 @docs/xxx.md 引用"
            )
    return warnings

def main():
    print("=" * 60)
    print("【Git Diff】")
    print(get_diff() or "(无变更)")

    changed = get_changed_files()
    print("\n【变更文件】")
    for f in changed:
        print(f"  {f}")

    missing_tests = find_missing_tests(changed)
    print("\n【缺少单测的模块】")
    if missing_tests:
        for m in missing_tests:
            print(f"  ⚠️  {m}")
    else:
        print("  ✅ 无缺失")

    claude_warnings = check_claude_md()
    print("\n【CLAUDE.md 大小检查】")
    if claude_warnings:
        for w in claude_warnings:
            print(f"  ⚠️  {w}")
    else:
        print("  ✅ 大小正常")

    print("=" * 60)

if __name__ == "__main__":
    os.chdir(Path(__file__).parents[3])  # 切到项目根目录
    main()

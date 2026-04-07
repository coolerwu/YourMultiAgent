#!/usr/bin/env python3
"""
Lightweight pre-commit inspection script for the YourMultiAgent repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def print_section(title: str, content: str) -> None:
    print(f"\n=== {title} ===")
    print(content if content else "(empty)")


def guess_missing_tests(changed_files: list[str]) -> list[str]:
    missing: list[str] = []

    for path_str in changed_files:
        path = Path(path_str)

        if path.suffix == ".py" and path.parts and path.parts[0] == "server":
            if "tests" in path.parts:
                continue
            expected = Path("server/tests").joinpath(*path.parts[1:-1], f"test_{path.stem}.py")
            if not (ROOT / expected).exists():
                missing.append(f"{path_str} -> missing {expected}")

        if path.suffix in {".js", ".jsx", ".ts", ".tsx"} and "web" in path.parts:
            if path.name.endswith((".test.js", ".test.jsx", ".test.ts", ".test.tsx")):
                continue
            expected = path.with_name(f"{path.stem}.test{path.suffix}")
            if not (ROOT / expected).exists():
                missing.append(f"{path_str} -> missing {expected}")

    return missing


def main() -> int:
    staged = run_git("diff", "--cached", "--name-only")
    unstaged = run_git("diff", "--name-only")
    changed_files = sorted({line for line in (staged + "\n" + unstaged).splitlines() if line})

    print_section("Git Diff", run_git("diff", "HEAD"))
    print_section("Changed Files", "\n".join(changed_files))

    missing_tests = guess_missing_tests(changed_files)
    print_section("Possible Missing Tests", "\n".join(missing_tests))

    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        line_count = sum(1 for _ in claude_md.open("r", encoding="utf-8"))
        warning = f"CLAUDE.md lines: {line_count}"
        if line_count > 200:
            warning += " (consider splitting details into docs/)"
        print_section("CLAUDE.md Size", warning)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

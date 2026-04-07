#!/bin/bash
# run_test.sh — 构建前端后以测试模式启动 Server
#
# 用法：
#   ./run_test.sh          # 构建 + 测试模式启动（端口 8080）
#   ./run_test.sh 9090     # 构建 + 测试模式启动（端口 9090）

set -e

PORT="${1:-8080}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1：构建前端"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$SCRIPT_DIR/web"
npm run build

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2：启动 Server（测试模式）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$SCRIPT_DIR"
exec ./run.sh test "$PORT"

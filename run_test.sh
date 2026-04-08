#!/bin/bash
# run_test.sh — 构建前端后以测试模式启动 Server
#
# 用法：
#   ./run_test.sh          # 构建 + 测试模式启动（端口 8080）
#   ./run_test.sh 9090     # 构建 + 测试模式启动（端口 9090）

set -euo pipefail

PORT="${1:-8080}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1：构建前端"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$SCRIPT_DIR/web"
if [ ! -d "node_modules" ]; then
  echo "缺少 web/node_modules，请先执行 cd web && npm install"
  exit 1
fi
npm run build

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2：启动 Server（首次运行会自动准备 Python 依赖）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$SCRIPT_DIR"
exec bash ./run.sh test "$PORT"

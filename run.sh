#!/bin/bash
# run.sh — YourMultiAgent 启动脚本
#
# 用法：
#   ./run.sh            # 生产模式，数据目录 ~/.yourmultiagent/
#   ./run.sh test       # 测试模式，数据目录 ./data/
#   ./run.sh test 9090  # 测试模式，指定端口

set -e

MODE="${1:-prod}"
PORT="${2:-8080}"

case "$MODE" in
  test)
    DATA_DIR="$(pwd)/data"
    mkdir -p "$DATA_DIR"
    echo "▶  启动（测试模式）"
    echo "   数据目录：$DATA_DIR"
    echo "   地址：http://0.0.0.0:$PORT"
    DATA_DIR="$DATA_DIR" python3 -m uvicorn server.main:app \
      --host 0.0.0.0 --port "$PORT" --reload
    ;;
  prod)
    DATA_DIR="$HOME/.yourmultiagent"
    mkdir -p "$DATA_DIR"
    echo "▶  启动（生产模式）"
    echo "   数据目录：$DATA_DIR"
    echo "   地址：http://0.0.0.0:$PORT"
    DATA_DIR="$DATA_DIR" python3 -m uvicorn server.main:app \
      --host 0.0.0.0 --port "$PORT"
    ;;
  *)
    echo "用法：$0 [prod|test] [PORT]"
    echo "  prod  生产模式（默认），数据存储在 ~/.yourmultiagent/"
    echo "  test  测试模式，数据存储在 ./data/"
    exit 1
    ;;
esac

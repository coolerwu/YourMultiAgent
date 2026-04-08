#!/bin/bash
# run.sh — YourMultiAgent 启动与快速部署脚本
#
# 用法：
#   ./run.sh prod [PORT]        # 拉取/更新仓库、安装依赖、注册 systemd，并启动服务
#   ./run.sh serve-prod [PORT]  # 仅启动生产服务（供 systemd 调用）
#   ./run.sh test [PORT]        # 测试模式，数据目录 ./data/

set -euo pipefail

MODE="${1:-prod}"
PORT="${2:-8080}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REPO_URL="https://github.com/coolerwu/YourMultiAgent.git"
ARCHIVE_URL="https://github.com/coolerwu/YourMultiAgent/archive/refs/heads/main.tar.gz"
SERVICE_NAME="yourmultiagent"
DEPLOY_DIR="${HOME}/yourmultiagent"
DATA_DIR_PROD="${HOME}/.yourmultiagent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

RUNTIME_PACKAGES=(
  "langgraph"
  "setuptools"
  "wheel"
)


require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令：$1"
    exit 1
  fi
}


resolve_python_bin() {
  if [ -x "$(pwd)/.venv/bin/python" ]; then
    printf '%s\n' "$(pwd)/.venv/bin/python"
  else
    printf '%s\n' "python3"
  fi
}


ensure_runtime_env() {
  local app_dir="$1"
  local venv_python="$app_dir/.venv/bin/python"
  local venv_pip="$app_dir/.venv/bin/pip"

  if [ ! -d "$app_dir/.venv" ]; then
    echo "▶  创建虚拟环境"
    python3 -m venv "$app_dir/.venv"
  fi

  echo "▶  安装运行时依赖"
  "$venv_pip" install --upgrade pip
  "$venv_pip" install --no-cache-dir -e "$app_dir"
  "$venv_pip" install --no-cache-dir "${RUNTIME_PACKAGES[@]}"

  if [ ! -x "$venv_python" ]; then
    echo "虚拟环境 Python 不存在：$venv_python"
    exit 1
  fi
}


run_uvicorn() {
  local data_dir="$1"
  local reload_flag="${2:-false}"
  local python_bin
  python_bin="$(resolve_python_bin)"

  mkdir -p "$data_dir"
  echo "▶  启动"
  echo "   Python：$python_bin"
  echo "   数据目录：$data_dir"
  echo "   地址：http://0.0.0.0:$PORT"

  if [ "$reload_flag" = "true" ]; then
    DATA_DIR="$data_dir" "$python_bin" -m uvicorn server.main:app \
      --host 0.0.0.0 --port "$PORT" --reload
  else
    DATA_DIR="$data_dir" "$python_bin" -m uvicorn server.main:app \
      --host 0.0.0.0 --port "$PORT"
  fi
}


ensure_deploy_repo() {
  mkdir -p "$DATA_DIR_PROD"
  mkdir -p "$DEPLOY_DIR"

  if command -v git >/dev/null 2>&1 && [ -d "$DEPLOY_DIR/.git" ]; then
    echo "▶  更新仓库：$DEPLOY_DIR"
    git -C "$DEPLOY_DIR" fetch --all --prune
    git -C "$DEPLOY_DIR" pull --ff-only
  elif command -v git >/dev/null 2>&1; then
    if [ -n "$(find "$DEPLOY_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
      local backup_dir="${DEPLOY_DIR}.bak-$(date +%Y%m%d-%H%M%S)"
      echo "▶  备份非 Git 部署目录：$DEPLOY_DIR -> $backup_dir"
      mv "$DEPLOY_DIR" "$backup_dir"
      mkdir -p "$DEPLOY_DIR"
    fi
    rmdir "$DEPLOY_DIR" 2>/dev/null || true
    echo "▶  克隆仓库：$REPO_URL -> $DEPLOY_DIR"
    git clone "$REPO_URL" "$DEPLOY_DIR"
  else
    require_cmd curl
    require_cmd tar
    download_repo_archive
  fi

  chmod +x "$DEPLOY_DIR/run.sh" 2>/dev/null || true
}


download_repo_archive() {
  local tmp_archive tmp_dir archive_root
  tmp_archive="$(mktemp)"
  tmp_dir="$(mktemp -d)"

  echo "▶  下载源码包：$ARCHIVE_URL"
  curl -L "$ARCHIVE_URL" -o "$tmp_archive"

  rm -rf "$DEPLOY_DIR"
  mkdir -p "$DEPLOY_DIR"
  tar -xzf "$tmp_archive" -C "$tmp_dir"

  archive_root="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [ -z "$archive_root" ]; then
    echo "源码包解压失败"
    rm -f "$tmp_archive"
    rm -rf "$tmp_dir"
    exit 1
  fi

  cp -R "$archive_root"/. "$DEPLOY_DIR"/
  rm -f "$tmp_archive"
  rm -rf "$tmp_dir"
}


write_service_file() {
  local tmp_file
  tmp_file="$(mktemp)"

  cat >"$tmp_file" <<EOF
[Unit]
Description=YourMultiAgent
After=network.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$DEPLOY_DIR
ExecStart=/bin/bash $DEPLOY_DIR/run.sh serve-prod $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  sudo mv "$tmp_file" "$SERVICE_FILE"
}


service_needs_update() {
  local tmp_file
  tmp_file="$(mktemp)"

  cat >"$tmp_file" <<EOF
[Unit]
Description=YourMultiAgent
After=network.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$DEPLOY_DIR
ExecStart=$DEPLOY_DIR/run.sh serve-prod $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  if [ ! -f "$SERVICE_FILE" ]; then
    rm -f "$tmp_file"
    return 0
  fi

  if ! sudo cmp -s "$tmp_file" "$SERVICE_FILE"; then
    rm -f "$tmp_file"
    return 0
  fi

  rm -f "$tmp_file"
  return 1
}


ensure_systemd_service() {
  require_cmd sudo
  require_cmd systemctl

  if [ ! -f "$SERVICE_FILE" ]; then
    echo "▶  注册 systemd 服务：$SERVICE_NAME"
    write_service_file
    sudo systemctl daemon-reload
    sudo systemctl enable --now "$SERVICE_NAME"
  elif service_needs_update; then
    echo "▶  更新 systemd 服务：$SERVICE_NAME"
    write_service_file
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE_NAME"
  else
    echo "▶  重启 systemd 服务：$SERVICE_NAME"
    sudo systemctl restart "$SERVICE_NAME"
  fi
}


verify_service() {
  echo "▶  验证服务状态"
  sleep 2
  systemctl status "$SERVICE_NAME" --no-pager || true
  python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:${PORT}/api/health', timeout=5).read().decode())"
}


deploy_prod() {
  require_cmd python3

  ensure_deploy_repo
  ensure_runtime_env "$DEPLOY_DIR"
  ensure_systemd_service
  verify_service
}


case "$MODE" in
  test)
    ensure_runtime_env "$SCRIPT_DIR"
    cd "$SCRIPT_DIR"
    run_uvicorn "$(pwd)/data" "true"
    ;;
  serve-prod)
    cd "$DEPLOY_DIR"
    run_uvicorn "$DATA_DIR_PROD" "false"
    ;;
  prod)
    deploy_prod
    ;;
  *)
    echo "用法：$0 [prod|serve-prod|test] [PORT]"
    echo "  prod        快速部署并启动 systemd 服务"
    echo "  serve-prod  仅启动生产服务（供 systemd 调用）"
    echo "  test        测试模式，数据存储在 ./data/"
    exit 1
    ;;
esac

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$ROOT_DIR/start-all-mac.config.yaml"

get_config() {
  /usr/bin/python3 - "$CONFIG_FILE" "$1" <<'PY'
import re
import sys

config_path, key = sys.argv[1], sys.argv[2]
pattern = re.compile(rf"^{re.escape(key)}:\s*(.*)$")

with open(config_path, "r", encoding="utf-8") as fp:
    for raw in fp:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        matched = pattern.match(line)
        if not matched:
            continue
        value = matched.group(1).strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        print(value)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

log() {
  printf '[start-all-mac] %s\n' "$1"
}

require_file() {
  if [[ ! -f "$1" ]]; then
    log "缺少文件: $1"
    exit 1
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "缺少命令: $1"
    exit 1
  fi
}

is_port_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_http_ready() {
  local url="$1"
  local timeout="$2"
  local elapsed=0
  while (( elapsed < timeout )); do
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' "$url" || true)"
    if [[ "$code" != "000" ]]; then
      return 0
    fi
    sleep 1
    ((elapsed+=1))
  done
  return 1
}

select_python() {
  if [[ -x "$ROOT_DIR/ai-service/.venv311/bin/python" ]]; then
    echo "$ROOT_DIR/ai-service/.venv311/bin/python"
    return
  fi
  if [[ -x "$ROOT_DIR/ai-service/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/ai-service/.venv/bin/python"
    return
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi
  command -v python3
}

frontend_url="$(get_config frontend_url)"
frontend_port="$(get_config frontend_port)"
backend_port="$(get_config backend_port)"
ai_port="$(get_config ai_port)"
mysql_host="$(get_config mysql_host)"
mysql_port="$(get_config mysql_port)"
mysql_database="$(get_config mysql_database)"
mysql_user="$(get_config mysql_user)"
mysql_password="$(get_config mysql_password)"
mysql_data_dir_rel="$(get_config mysql_data_dir)"
mysql_socket_rel="$(get_config mysql_socket)"
mysql_pid_rel="$(get_config mysql_pid_file)"
run_dir_rel="$(get_config run_dir)"

RUN_DIR="$ROOT_DIR/$run_dir_rel"
MYSQL_DATA_DIR="$ROOT_DIR/$mysql_data_dir_rel"
MYSQL_SOCKET="$ROOT_DIR/$mysql_socket_rel"
MYSQL_PID_FILE="$ROOT_DIR/$mysql_pid_rel"
AI_LOG="$RUN_DIR/ai-service.log"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"
AI_ENV_FILE="$ROOT_DIR/ai-service/.env.local"

mkdir -p "$RUN_DIR"

require_file "$CONFIG_FILE"
require_cmd curl
require_cmd npm
require_cmd mvn
require_cmd lsof

if [[ -z "${JAVA_HOME:-}" ]] && [[ -x /usr/libexec/java_home ]]; then
  export JAVA_HOME="$(/usr/libexec/java_home 2>/dev/null || true)"
fi

if [[ -n "${JAVA_HOME:-}" ]]; then
  export PATH="$JAVA_HOME/bin:/opt/homebrew/bin:$PATH"
else
  export PATH="/opt/homebrew/bin:$PATH"
fi

PYTHON_BIN="$(select_python)"
MYSQLD_BIN="${MYSQLD_BIN:-/opt/homebrew/opt/mysql/bin/mysqld}"
MYSQL_BIN="${MYSQL_BIN:-/opt/homebrew/opt/mysql/bin/mysql}"
MYSQLADMIN_BIN="${MYSQLADMIN_BIN:-/opt/homebrew/opt/mysql/bin/mysqladmin}"

if [[ ! -x "$MYSQLD_BIN" || ! -x "$MYSQL_BIN" || ! -x "$MYSQLADMIN_BIN" ]]; then
  log "未找到 MySQL 可执行文件，请先安装 Homebrew mysql。"
  exit 1
fi

require_file "$ROOT_DIR/backend/sql/schema.sql"

run_mysql() {
  if [[ -n "$mysql_password" ]]; then
    "$MYSQL_BIN" -h"$mysql_host" -P"$mysql_port" -u"$mysql_user" -p"$mysql_password" "$@"
  else
    "$MYSQL_BIN" -h"$mysql_host" -P"$mysql_port" -u"$mysql_user" "$@"
  fi
}

run_mysqladmin() {
  if [[ -n "$mysql_password" ]]; then
    "$MYSQLADMIN_BIN" -h"$mysql_host" -P"$mysql_port" -u"$mysql_user" -p"$mysql_password" "$@"
  else
    "$MYSQLADMIN_BIN" -h"$mysql_host" -P"$mysql_port" -u"$mysql_user" "$@"
  fi
}

ensure_mysql_initialized() {
  mkdir -p "$MYSQL_DATA_DIR"
  if [[ -d "$MYSQL_DATA_DIR/mysql" ]]; then
    return
  fi
  log "初始化项目私有 MySQL 数据目录..."
  "$MYSQLD_BIN" \
    --initialize-insecure \
    --basedir="/opt/homebrew/opt/mysql" \
    --datadir="$MYSQL_DATA_DIR" \
    --user="$(whoami)"
}

ensure_mysql_started() {
  if is_port_listening "$mysql_port"; then
    log "MySQL 已在端口 $mysql_port 运行，复用现有实例。"
    return
  fi

  ensure_mysql_initialized

  log "启动项目私有 MySQL..."
  "$MYSQLD_BIN" \
    --basedir="/opt/homebrew/opt/mysql" \
    --datadir="$MYSQL_DATA_DIR" \
    --port="$mysql_port" \
    --socket="$MYSQL_SOCKET" \
    --pid-file="$MYSQL_PID_FILE" \
    --bind-address="$mysql_host" \
    --daemonize

  for _ in {1..20}; do
    if run_mysqladmin ping >/dev/null 2>&1; then
      log "MySQL 启动完成。"
      return
    fi
    sleep 1
  done

  log "MySQL 启动超时。"
  exit 1
}

ensure_database_schema() {
  local db_exists
  db_exists="$(run_mysql -Nse "SHOW DATABASES LIKE '$mysql_database';" || true)"
  if [[ "$db_exists" == "$mysql_database" ]]; then
    log "数据库 $mysql_database 已存在，跳过建库。"
    return
  fi

  log "导入数据库结构..."
  run_mysql < "$ROOT_DIR/backend/sql/schema.sql"
}

start_ai_service() {
  if wait_http_ready "http://127.0.0.1:${ai_port}/ai/health" 2; then
    log "AI 服务已运行，跳过启动。"
    return
  fi

  log "启动 AI 服务..."
  (
    cd "$ROOT_DIR/ai-service"
    nohup env PYTHONPATH=. AI_PORT="$ai_port" AI_ENV_FILE="$AI_ENV_FILE" "$PYTHON_BIN" -c '
import os
from dotenv import load_dotenv
import uvicorn

env_file = os.environ.get("AI_ENV_FILE")
if env_file and os.path.exists(env_file):
    load_dotenv(env_file, override=True)

uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["AI_PORT"]))
' >"$AI_LOG" 2>&1 &
  )

  wait_http_ready "http://127.0.0.1:${ai_port}/ai/health" 60 || {
    log "AI 服务启动失败，请查看日志: $AI_LOG"
    exit 1
  }
}

start_backend() {
  if wait_http_ready "http://127.0.0.1:${backend_port}/actuator/health" 2; then
    log "Backend 已运行，跳过启动。"
    return
  fi

  log "启动 Backend..."
  (
    cd "$ROOT_DIR/backend"
    nohup env \
      DB_URL="jdbc:mysql://${mysql_host}:${mysql_port}/${mysql_database}?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true" \
      DB_USERNAME="$mysql_user" \
      DB_PASSWORD="$mysql_password" \
      AI_SERVICE_BASE_URL="http://127.0.0.1:${ai_port}" \
      AI_SERVICE_URL="http://127.0.0.1:${ai_port}/ai/api/v1/generate/async" \
      AI_CALLBACK_URL="http://127.0.0.1:${backend_port}/api/v1/poetry/callback" \
      AI_CALLBACK_TOKEN="poetry-callback-token-change-me" \
      mvn spring-boot:run >"$BACKEND_LOG" 2>&1 &
  )

  wait_http_ready "http://127.0.0.1:${backend_port}/actuator/health" 120 || {
    log "Backend 启动失败，请查看日志: $BACKEND_LOG"
    exit 1
  }
}

start_frontend() {
  if wait_http_ready "$frontend_url" 2; then
    log "Frontend 已运行，跳过启动。"
    return
  fi

  log "启动 Frontend..."
  (
    cd "$ROOT_DIR/frontend"
    nohup npm run dev -- --host 127.0.0.1 --port "$frontend_port" >"$FRONTEND_LOG" 2>&1 &
  )

  wait_http_ready "$frontend_url" 60 || {
    log "Frontend 启动失败，请查看日志: $FRONTEND_LOG"
    exit 1
  }
}

main() {
  log "使用配置文件: $CONFIG_FILE"
  log "Python: $PYTHON_BIN"
  log "开始启动全部服务..."

  ensure_mysql_started
  ensure_database_schema
  start_ai_service
  start_backend
  start_frontend

  log "全部服务已就绪。"
  log "Frontend: $frontend_url"
  log "Backend : http://127.0.0.1:${backend_port}/actuator/health"
  log "AI      : http://127.0.0.1:${ai_port}/ai/health"
  log "日志目录: $RUN_DIR"

  open "$frontend_url" >/dev/null 2>&1 || true
}

main "$@"

#!/usr/bin/env bash
# 重启后端 API：停掉占用端口的旧 uvicorn，再后台拉起新进程。
# 用法：scripts/restart_api.sh（可用 API_PORT 覆盖端口，默认 8080）
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${API_PORT:-8080}"
LOG_FILE="logs/uvicorn.out"

# ── 停旧进程：按端口找 PID，先 TERM 优雅退出，3 秒后仍在则 KILL ──
PIDS="$(lsof -ti "tcp:${PORT}" || true)"
if [ -n "$PIDS" ]; then
    echo "停止端口 ${PORT} 上的旧进程: $PIDS"
    kill $PIDS 2>/dev/null || true
    for _ in 1 2 3; do
        sleep 1
        lsof -ti "tcp:${PORT}" >/dev/null 2>&1 || break
    done
    REMAIN="$(lsof -ti "tcp:${PORT}" || true)"
    if [ -n "$REMAIN" ]; then
        echo "优雅退出超时，强制结束: $REMAIN"
        kill -9 $REMAIN 2>/dev/null || true
        sleep 1
    fi
else
    echo "端口 ${PORT} 无进程在运行"
fi

# ── 启动新进程（后台，stdout 落 logs/uvicorn.out，业务日志见 logs/api.log）──
mkdir -p logs
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
    >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "已启动 uvicorn (PID ${NEW_PID})，等待就绪…"

# ── 健康检查：最多等 10 秒 ──
for _ in $(seq 1 10); do
    sleep 1
    if curl -s -m 2 "http://127.0.0.1:${PORT}/healthz" | grep -q '"ok"'; then
        echo "✅ 后端已就绪: http://0.0.0.0:${PORT}（局域网可访问）"
        exit 0
    fi
done

echo "❌ ${PORT} 端口 10 秒内未就绪，请查看日志: ${LOG_FILE} / logs/api.log"
exit 1

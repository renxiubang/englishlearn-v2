#!/usr/bin/env bash
# 启动后端 API（uvicorn :8080）。前置：MySQL 已启动、已 alembic upgrade + seed。
set -euo pipefail
cd "$(dirname "$0")/.."

exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8080}"

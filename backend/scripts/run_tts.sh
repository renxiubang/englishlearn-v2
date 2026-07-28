#!/usr/bin/env bash
# 启动 Kokoro TTS 常驻服务（:8880，MLX 后端，首次会下载模型）。
# 依赖 tts extra：uv sync --extra tts
set -euo pipefail
cd "$(dirname "$0")/.."

exec uv run python tts_server/server.py

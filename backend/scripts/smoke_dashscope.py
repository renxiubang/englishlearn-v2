"""Qwen-Omni（dashscope）接口级联调冒烟脚本。

前置：MySQL 已启动 + 迁移/种子完成；后端 API 运行于 :8080
（uvicorn 进程 PATH 需含 ffmpeg/ffprobe）；.env 已配置 dashscope Key。

用法：cd backend && uv run python scripts/smoke_dashscope.py <wav_path>
串行执行 5 步，输出各步 PASS/FAIL 与返回摘要，任一步失败即退出码 1。
"""

import json
import sys

import httpx

BASE = "http://127.0.0.1:8080/api"
CONTACT = "dad"

passed: list[str] = []
failed: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    if cond:
        passed.append(name)
        print(f"  PASS  {name}  {detail}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}  {detail}")


def cut(s, n=80):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def main(wav_path: str) -> int:
    client = httpx.Client(timeout=180)

    # ── 1. GET /contacts：DB 连通与种子在位 ──────────────
    print("[1] GET /contacts")
    r = client.get(f"{BASE}/contacts")
    data = r.json().get("data") or []
    check("contacts", r.status_code == 200 and any(c.get("id") == CONTACT for c in data),
          f"{len(data)} contacts")

    # ── 2. 5a 文本消息：reply 含 en、不含 zh ─────────────
    print("[2] 5a POST text message")
    r = client.post(f"{BASE}/chats/{CONTACT}/messages",
                    json={"text": "Hello dad, what are we having for dinner?"})
    reply = (r.json().get("data") or {}).get("reply") or {}
    check("5a reply.en", r.status_code == 200 and bool(reply.get("en")),
          cut(reply.get("en", "")))
    check("5a no zh", "zh" not in reply, f"keys={sorted(reply.keys())}")

    # ── 3. 5b 语音 SSE：事件序 + TTS 降级 + raw ──────────
    print("[3] 5b POST voice message (SSE)")
    events: list[tuple[str, dict]] = []
    with open(wav_path, "rb") as f:
        with client.stream(
            "POST", f"{BASE}/chats/{CONTACT}/messages",
            files={"audio": ("record.wav", f, "audio/wav")},
        ) as resp:
            check("5b status/SSE", resp.status_code == 200
                  and resp.headers.get("content-type", "").startswith("text/event-stream"),
                  f"status={resp.status_code}")
            event_name = None
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:") and event_name:
                    try:
                        payload = json.loads(line[5:].strip() or "{}")
                    except json.JSONDecodeError:
                        payload = {}
                    events.append((event_name, payload))
                    event_name = None

    names = [n for n, _ in events]
    by = dict(events)  # 同名事件取最后一条（delta 只看存在性）
    print(f"      events: {names}")
    check("5b event order",
          names[0:1] == ["reply_start"] and names[-1:] == ["done"]
          and "reply_delta" in names and "reply_end" in names
          and "user_en" in names and "user_bubble" in names
          and "user_zh" not in names and "error" not in names)
    reply_end = by.get("reply_end", {})
    check("5b TTS degrade", reply_end.get("duration") is None and reply_end.get("url") is None,
          cut(reply_end))
    user_en = by.get("user_en", {})
    check("5b user_en{en,raw}", bool(user_en.get("en")) and "raw" in user_en,
          f"en={cut(user_en.get('en', ''), 50)} raw={cut(user_en.get('raw', ''), 50)}")
    bubble = by.get("user_bubble", {})
    check("5b user_bubble", bool(bubble.get("id")) and "raw" in bubble and "zh" not in bubble,
          f"id={bubble.get('id')} keys={sorted(bubble.keys())}")
    me_id = bubble.get("id")

    # ── 4. 接口 19：按需翻译 + 幂等 ──────────────────────
    print("[4] POST /messages/{id}/translate")
    if me_id:
        r1 = client.post(f"{BASE}/messages/{me_id}/translate")
        zh1 = (r1.json().get("data") or {}).get("zh", "")
        check("19 zh", r1.status_code == 200 and bool(zh1), cut(zh1))
        r2 = client.post(f"{BASE}/messages/{me_id}/translate")
        zh2 = (r2.json().get("data") or {}).get("zh", "")
        check("19 idempotent", zh2 == zh1)
    else:
        check("19 zh", False, "no user_bubble.id from step 3")

    # ── 5. 历史消息：raw/zh 落库 ─────────────────────────
    print("[5] GET /chats/{id}/messages")
    r = client.get(f"{BASE}/chats/{CONTACT}/messages")
    msgs = (r.json().get("data") or {}).get("list") or []
    me = next((m for m in msgs if m.get("id") == me_id), None)
    check("hist raw persisted", bool(me and me.get("raw")), cut(me.get("raw", "")) if me else "msg not found")
    check("hist zh persisted", bool(me and me.get("zh")), cut(me.get("zh", "")) if me else "")

    print(f"\n{'ALL PASS' if not failed else 'FAILED'}: {len(passed)} passed, {len(failed)} failed")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: uv run python scripts/smoke_dashscope.py <wav_path>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

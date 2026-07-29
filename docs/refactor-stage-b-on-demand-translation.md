# 改造计划：阶段B 结构化输出 + 按需翻译

> 状态：已确认，按"文档先行"顺序执行。契约定稿见 [api.md](./api.md)，设计定稿见 [architecture.md](./architecture.md)。

## 需求摘要

- 5b 阶段B：用户语音一次性送多模态大模型，模型输出 JSON `{"raw": 原始逐字转录, "en": 语法修正后英文}`，取消级联三调用与中文翻译；raw 下发前端，我方气泡展开区分两行显示"原译/纠译"。
- 改造范围为"两者都改"：AI 回复（5b 阶段A `reply_end`、5a 文本回复）也不再即时翻译；所有气泡的中文均在点击"翻译"按钮后经新接口按需生成，并落库供历史复用。

## 执行顺序（文档先行）

1. **文档定稿**：先改 api.md（契约：事件表/载荷/接口 19/数据形状）与 architecture.md（设计：单调用链路/时序图/降级策略），作为后续实现的唯一口径；不单独写 PRD（本文档承担需求描述职责）。
2. **后端实现**：提示词/网关（含云端 provider 兼容开关）→ 数据模型与迁移 → 编排器与路由 → 后端测试。
3. **前端实现**：类型/API 层 → ChatView SSE 分支 → ChatBubble 展示与翻译按钮。
4. **验证**：后端 pytest + 迁移升级、前端构建/类型检查、手动冒烟。

## 后端

### 提示词与网关

- `backend/app/prompts.yaml`：新增 `transcribe_correct` 提示词——转录英文语音并给出语法修正句，只输出 JSON `{"raw": "...", "en": "..."}`（对齐 `verify_semantic` 的 JSON 约束写法）；同步在 `backend/app/gateway/prompts.py` 的 `REQUIRED_KEYS` 中登记。原 `transcribe_en/zh`、`translate_*` 保留（16/17 接口与按需翻译仍用）。
- `backend/app/gateway/mllm.py`：新增 `transcribe_correct(audio_b64) -> tuple[str, str]`（返回 raw, en）。解析复用 `verify_semantic` 模式：正则取首个 `{...}` + `json.loads`；解析失败降级为 raw = en = 模型原文（strip 后），打 warning 日志。注：该方法为单次复合指令 + JSON 结构化输出，是对"单一职责纯文本"规范的有意例外（产品决策），在方法 docstring 中注明。

### 云端模型兼容开关（百炼 Qwen-Omni 临时替换本地 Gemma）

- `backend/app/core/config.py`：新增 `mllm_provider: str = "local"`（`local | dashscope`）；`backend/.env.example` 补 `MLLM_PROVIDER=local` 及百炼配置注释示例（`MLLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`、`MLLM_MODEL=qwen3-omni-flash`、API Key）。
- `backend/app/gateway/mllm.py` 按 provider 分支处理三个已核实差异（方法签名与上层调用不变，随时可切回本地）：
  - `_audio_part`：dashscope 时 `data` 加 `data:;base64,` 前缀；
  - `_payload`：dashscope 时去掉 `chat_template_kwargs`（本地 Gemma 专用），改加 `modalities: ["text"]`（只要文本输出）；
  - `_complete`：Qwen-Omni 所有请求必须 `stream=True`，dashscope 时内部改走 `_complete_stream` 聚合为完整文本返回，非流式语义对上层透明。
- 测试：新增 provider 分支单测（断言两种 provider 的 payload / audio_part 形态，不真调云端）。

### 编排器与路由

- `backend/app/modules/chat/orchestrator.py`：
  - 阶段A：删除 `reply_zh` 翻译调用；`reply_end` 载荷改为 `{duration, url}`（去掉 zh）；落库 `msg.zh` 保持空串。
  - 阶段B：级联三调用替换为单次 `transcribe_correct`；删除 `user_zh` 事件；`user_en` 载荷改为 `{en, raw}`；落库我方消息 `en=纠译, raw=原译, zh=""`；`user_bubble` 载荷改为 `{id, en, raw, userAudio, ttsAudio}`（去掉 zh）；更新模块 docstring。
- `backend/app/modules/chat/router.py`：
  - 5a：删除 `translate(reply_en, "en_to_zh")` 调用，响应 `reply` 不再含 zh。
  - 新增接口 19 `POST /api/messages/{message_id}/translate`（同文件）：查消息（无则 404）；`msg.zh` 已有值直接返回；否则 `mllm.translate(msg.en, "en_to_zh")` → 写回 `msg.zh` 落库 → 返回 `ok({zh})`；`msg.en` 为空返回 400。

### 数据模型与迁移

- `backend/app/models/tables.py`：`Message` 新增 `raw: Mapped[str] = mapped_column(Text, default="")`（我方语音消息的原始转录，其余消息为空）。
- `backend/app/modules/chat/repository.py`：`insert_message` 增加 `raw` 参数；`message_to_dict` 在 raw 非空时输出 `raw` 字段（历史消息接口 4 自动带出）。
- 新增 alembic 迁移：`messages` 表加 `raw` 列（Text，服务端默认空串）。

### 测试

- 新增 `backend/tests/test_transcribe_correct_parse.py`（与 test_verify_parse 同风格）：覆盖正常 JSON、带包裹文本的 JSON、解析失败降级三种情况。
- `backend/tests/test_prompts.py` 依赖的 `REQUIRED_KEYS` 更新后自动覆盖新键。

## 前端

- `web/src/types/index.ts`：`ChatMessage` 加 `raw?: string`；`UserBubblePayload` 去 zh、加 raw；`ChatReply.zh` 改为可选。
- `web/src/api/index.ts`：`chatApi` 新增 `translateMessage(id: number) => http.post<{ zh: string }>('/messages/' + id + '/translate')`。
- `web/src/views/ChatView.vue`：
  - SSE 分支：删除 `user_zh` case；`user_en` 回填 `pendingMsg.en/raw`；`reply_end` 不再读 zh；`user_bubble` 回填 raw（不再回填 zh）。
  - 新增 `onTranslate(m)` 处理器：`m.zh` 已有或 `m.id < 0`（本地临时气泡）时跳过，否则调 `translateMessage(m.id)` 回填 `m.zh`，失败 toast；模板给两处 `ChatBubble` 传 `:raw="m.raw"` 并监听 `@translate="onTranslate(m)"`。
- `web/src/components/ChatBubble.vue`：
  - 新增 `raw?: string` prop 与 `translate` emit；me 语音气泡展开区当 raw 非空时分两行显示"原译：{raw}"与"纠译：{en}"，否则维持单行 en；them 气泡展开区不变。
  - "翻译"按钮（两侧通用）：点击时若 `zh` 为空则 emit `translate` 并置 `zhShown=true`，zh 到达前显示"翻译中…"占位；`zh` 已有则维持现状切换显隐。`warnOnTranslate` 警示逻辑不变。
  - 收藏行为不变：zh 未翻译时收藏的 zh 为空串（既有 favorites 契约允许）。
- mock 层（`web/mock/`）不涉及 chat/messages 路由，无需改动。

## 文档（职责分离：api.md 契约 / architecture.md 实现）

- [api.md](./api.md)：
  - 5b 事件表与示例流：删 `user_zh` 行；`user_en` 载荷 `{en, raw}`；`reply_end` 载荷 `{duration, url}`；`user_bubble` 载荷 `{id, en, raw, userAudio, ttsAudio}`；两阶段流程描述同步更新。
  - 5a 响应示例去 zh；ChatMessage 数据形状补 `raw`（可选）、注明 zh 按需生成。
  - 接口总表与详情新增接口 19 `POST /api/messages/{messageId}/translate`（入参、响应 `{zh}`、404/400 语义、幂等说明）。
- [architecture.md](./architecture.md)：
  - §1.4 级联调用模式说明改写：阶段B 为单次 JSON 结构化调用（raw+en），标注为单一职责规范的有意例外及解析降级策略。
  - §2.2 流水线步骤、§2.3 时序图更新（阶段B 单调用、无 user_zh；raw 已下发不再是内部中间产物）；接口 19 按需翻译链路补一句说明。
  - 网关模块清单补 `transcribe_correct`；输出格式约定小节补充第二个 JSON 结构化输出；错误处理表将 `transcribe_correct` 纳入"非流式幂等重试 1 次"范围。
  - §2.5 厂商隔离行补 `MLLM_PROVIDER`（`local | dashscope`）兼容开关设计说明（三处差异适配）。
- `messages` 表结构文档（architecture.md 表定义处）补 `raw` 列。

## 验证

- 后端：`uv run pytest`（backend 目录）；alembic 迁移可正常升级。
- 前端：`npm run build`（或 vue-tsc 类型检查）确认类型改动无误。
- 手动冒烟（需本地 MLLM/TTS 服务在位时）：发一条语音消息，确认我方气泡显示原译/纠译两行、点击"翻译"后中文出现且刷新页面（历史接口）后仍在。
- 云端切换冒烟（可选，需百炼 API Key）：`MLLM_PROVIDER=dashscope` 后跑一轮 5b 与接口 19，确认三处差异适配生效。

## 假设

- 存量消息已有 zh 的继续直接展示；新消息 zh 一律按需生成。
- 接口 17（verify_semantic）与接口 16（辅助卡片）链路不动，仍用原 `transcribe`/`translate`。
- 云端替换为开发期临时手段，默认 provider 仍为 `local`；TTS 仍走本地 Kokoro，不在本次范围。

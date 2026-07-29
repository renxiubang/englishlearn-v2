import Foundation

/// 直连多模态模型客户端（M4，对齐 backend/app/gateway/mllm.py 的 dashscope provider 分支）。
/// 三处差异：① input_audio.data 加 `data:;base64,` 前缀；② payload 传 modalities:["text"]
/// 而非 chat_template_kwargs；③ qwen3-omni-flash 仅支持流式，非流式方法内部收流聚合。
@MainActor
final class DirectMLLMClient {
    private let settings: AppSettings

    init(settings: AppSettings) {
        self.settings = settings
    }

    /// 上下文消息：["role": "user"|"assistant", "content": <文本>]
    typealias Context = [[String: String]]

    private var apiKey: String { KeychainStore.load(.dashscopeAPIKey) ?? "" }

    private var chatURL: URL? {
        var base = settings.dashscopeBaseURL
        if base.hasSuffix("/") { base.removeLast() }
        return URL(string: base + "/chat/completions")
    }

    // MARK: - 底层调用

    private func audioPart(_ audioB64: String) -> [String: Any] {
        // dashscope（百炼 Qwen-Omni）要求 base64 带 data URI 前缀
        ["type": "input_audio",
         "input_audio": ["data": "data:;base64,\(audioB64)", "format": "wav"]]
    }

    private func payload(_ messages: [[String: Any]], stream: Bool, maxTokens: Int) -> [String: Any] {
        var p: [String: Any] = [
            "model": settings.modelName,
            "messages": messages,
            "max_tokens": maxTokens,
            "temperature": 0.0,
            // Qwen-Omni：只要文本输出（无 chat_template_kwargs，那是本地 Gemma 专用）
            "modalities": ["text"],
        ]
        if stream { p["stream"] = true }
        return p
    }

    /// 流式补全，逐 token 产出（OpenAI 兼容 SSE：data: {...}，[DONE] 结束，reasoning_content 回退）
    private func completeStream(_ messages: [[String: Any]], maxTokens: Int)
        -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    guard let url = chatURL else { throw APIError.invalidResponse }
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    request.timeoutInterval = 120
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
                    request.httpBody = try JSONSerialization.data(
                        withJSONObject: payload(messages, stream: true, maxTokens: maxTokens))

                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                        var body = Data()
                        for try await b in bytes { body.append(b) }
                        let msg = String(data: body, encoding: .utf8) ?? "直连模型请求失败"
                        throw APIError.business(code: http.statusCode, message: msg)
                    }
                    for try await line in bytes.lines {
                        guard line.hasPrefix("data:") else { continue }
                        let s = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                        if s == "[DONE]" { break }
                        guard let data = s.data(using: .utf8),
                              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                              let choices = obj["choices"] as? [[String: Any]],
                              let delta = choices.first?["delta"] as? [String: Any] else { continue }
                        let token = (delta["content"] as? String)
                            ?? (delta["reasoning_content"] as? String) ?? ""
                        if !token.isEmpty { continuation.yield(token) }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    /// 非流式补全：dashscope 仅支持流式，内部收流聚合对上层透明
    private func complete(_ messages: [[String: Any]], maxTokens: Int) async throws -> String {
        var parts: [String] = []
        for try await token in completeStream(messages, maxTokens: maxTokens) { parts.append(token) }
        return parts.joined().trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func systemMessage(_ content: String) -> [String: Any] {
        ["role": "system", "content": content]
    }

    private func contextMessages(_ context: Context) -> [[String: Any]] {
        context.map { ["role": $0["role"] ?? "user", "content": $0["content"] ?? ""] }
    }

    // MARK: - 业务方法（对齐 mllm.py）

    /// 对话回复（5b 阶段A）：流式输出英文回复文本
    func replyStream(personaPrompt: String, context: Context, audioB64: String)
        -> AsyncThrowingStream<String, Error> {
        let system = "\(personaPrompt.trimmingCharacters(in: .whitespacesAndNewlines))\n\n\(PromptsLoader.get("chat_reply"))"
        var messages: [[String: Any]] = [systemMessage(system)]
        messages.append(contentsOf: contextMessages(context))
        messages.append([
            "role": "user",
            "content": [["type": "text", "text": "(voice message)"], audioPart(audioB64)],
        ])
        return completeStream(messages, maxTokens: 256)
    }

    /// 对话回复（5a 文本）：非流式
    func replyText(personaPrompt: String, context: Context, text: String) async throws -> String {
        let system = "\(personaPrompt.trimmingCharacters(in: .whitespacesAndNewlines))\n\n\(PromptsLoader.get("chat_reply"))"
        var messages: [[String: Any]] = [systemMessage(system)]
        messages.append(contentsOf: contextMessages(context))
        messages.append(["role": "user", "content": text])
        return try await complete(messages, maxTokens: 256)
    }

    /// 音频→原文转录（级联阶段一）。lang: "en" | "zh"
    func transcribe(audioB64: String, lang: String) async throws -> String {
        let messages: [[String: Any]] = [
            systemMessage(PromptsLoader.get("transcribe_\(lang)")),
            ["role": "user",
             "content": [["type": "text", "text": "Audio Transcription Task:"], audioPart(audioB64)]],
        ]
        return try await complete(messages, maxTokens: 512)
    }

    /// 转录+语法修正（5b 阶段B）：单次 JSON 结构化，返回 (raw 原译, en 纠译)
    func transcribeCorrect(audioB64: String) async throws -> (raw: String, en: String) {
        let messages: [[String: Any]] = [
            systemMessage(PromptsLoader.get("transcribe_correct")),
            ["role": "user",
             "content": [["type": "text", "text": "Audio Transcription Task:"], audioPart(audioB64)]],
        ]
        let output = try await complete(messages, maxTokens: 512)
        return Self.parseTranscribeCorrect(output)
    }

    /// 纯文本翻译（级联阶段二）。direction: "en_to_zh" | "zh_to_en"
    func translate(text: String, direction: String) async throws -> String {
        let messages: [[String: Any]] = [
            systemMessage(PromptsLoader.get("translate_\(direction)")),
            ["role": "user", "content": text],
        ]
        return try await complete(messages, maxTokens: 512)
    }

    /// 复读语义校验（接口 17）：级联转录 + JSON 判定；解析失败按不一致处理
    func verifySemantic(audioB64: String, targetEn: String) async throws -> (Bool, String?) {
        let transcription = try await transcribe(audioB64: audioB64, lang: "en")
        if transcription.isEmpty { return (false, "未能识别到语音内容，请再试一次") }
        let user = "Target sentence: \(targetEn)\nStudent's transcription: \(transcription)"
        let raw = try await complete([
            systemMessage(PromptsLoader.get("verify_semantic")),
            ["role": "user", "content": user],
        ], maxTokens: 128)
        guard let data = Self.extractJSON(raw) else {
            return (false, "复读内容与目标句语义不符，请再试一次")
        }
        let consistent = (data["consistent"] as? Bool) ?? false
        var reason = (data["reason"] as? String).flatMap { $0.isEmpty ? nil : $0 }
        if !consistent, reason == nil { reason = "复读内容与目标句语义不符，请再试一次" }
        return (consistent, consistent ? nil : reason)
    }

    // MARK: - JSON 解析（对齐 mllm.py 正则取首个 {...}）

    private static func extractJSON(_ text: String) -> [String: Any]? {
        guard let re = try? NSRegularExpression(pattern: "\\{.*\\}",
                                                options: [.dotMatchesLineSeparators]) else { return nil }
        let range = NSRange(text.startIndex..., in: text)
        guard let m = re.firstMatch(in: text, range: range),
              let r = Range(m.range, in: text) else { return nil }
        return (try? JSONSerialization.jsonObject(with: Data(text[r].utf8))) as? [String: Any]
    }

    /// 解析 transcribe_correct 的 JSON 输出，返回 (raw, en)；解析失败降级为模型原文
    static func parseTranscribeCorrect(_ rawOutput: String) -> (raw: String, en: String) {
        let text = rawOutput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let data = extractJSON(text) else { return (text, text) }
        let raw = (data["raw"] as? String ?? "").trimmingCharacters(in: .whitespaces)
        let en = (data["en"] as? String ?? "").trimmingCharacters(in: .whitespaces)
        if en.isEmpty { return ("", "") }
        return (raw.isEmpty ? en : raw, en)
    }
}

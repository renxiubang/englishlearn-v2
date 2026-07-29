import Foundation

/// 在线通道（架构文档 §3.2）：严格按 api.md 契约调用自建后端。
/// M1 覆盖接口 3/4/5a/18/19；M2 补齐 5b POST-SSE；M3 补齐 16/17 辅助卡片。
@MainActor
final class RemoteBackend: ChatBackend {
    private let settings: AppSettings
    private let http = HTTPClient()

    init(settings: AppSettings) {
        self.settings = settings
    }

    private func apiURL(_ path: String, query: [URLQueryItem] = []) throws -> URL {
        guard var components = URLComponents(string: settings.backendBaseURL) else {
            throw APIError.invalidResponse
        }
        components.path = "/api" + path
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else { throw APIError.invalidResponse }
        return url
    }

    // MARK: - 聊天

    /// 接口 4：游标分页历史消息
    func fetchMessages(contactId: String, cursor: Int64?, limit: Int) async throws -> MessagePage {
        var query = [URLQueryItem(name: "limit", value: String(limit))]
        if let cursor {
            query.append(URLQueryItem(name: "cursor", value: String(cursor)))
        }
        return try await http.get(apiURL("/chats/\(contactId)/messages", query: query))
    }

    /// 接口 5a：文本消息（同步）
    func sendText(contactId: String, text: String) async throws -> ChatReply {
        struct ReplyData: Decodable { let reply: ChatReply }
        let data: ReplyData = try await http.post(
            apiURL("/chats/\(contactId)/messages"), json: ["text": text])
        return data.reply
    }

    /// 接口 5b：语音消息 POST-SSE（multipart wav → 事件流，架构文档 §3.2）
    func sendVoice(contactId: String, wav: Data) -> AsyncThrowingStream<ChatSSEEvent, Error> {
        do {
            let url = try apiURL("/chats/\(contactId)/messages")
            var multipart = MultipartBody()
            multipart.addFile(name: "audio", filename: "voice.wav",
                              mimeType: "audio/wav", data: wav)
            return postSSE(url: url, multipart: multipart, map: Self.mapChatEvent) {
                if case .done = $0 { return true }
                return false
            }
        } catch {
            return AsyncThrowingStream { $0.finish(throwing: error) }
        }
    }

    /// POST-SSE 通用骨架（5b/16 共用）：建流前非 200 走 JSON 统一包裹；
    /// 手动按字节切行——bytes.lines 会吞掉空行，而 SSE 靠空行分帧。
    private func postSSE<Event>(
        url: URL,
        multipart: MultipartBody,
        map: @escaping @Sendable (SSEFrame) -> Event?,
        isDone: @escaping @Sendable (Event) -> Bool
    ) -> AsyncThrowingStream<Event, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    request.timeoutInterval = 120
                    request.setValue(multipart.contentType, forHTTPHeaderField: "Content-Type")
                    request.httpBody = multipart.finalized()

                    let (bytes, response) = try await URLSession.shared.bytes(for: request)

                    // 建流前错误（400/404/409/413/429）走 JSON 统一包裹
                    if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                        var body = Data()
                        for try await byte in bytes { body.append(byte) }
                        let _: EmptyPayload = try HTTPClient.decodeEnvelope(body)
                        throw APIError.invalidResponse
                    }

                    var parser = SSELineParser()
                    var lineBuf = [UInt8]()
                    stream: for try await byte in bytes {
                        guard byte == 0x0A else {
                            lineBuf.append(byte)
                            continue
                        }
                        if lineBuf.last == 0x0D { lineBuf.removeLast() }
                        let line = String(decoding: lineBuf, as: UTF8.self)
                        lineBuf.removeAll(keepingCapacity: true)
                        guard let frame = parser.feed(line: line),
                              let event = map(frame) else { continue }
                        continuation.yield(event)
                        if isDone(event) { break stream }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    /// SSE 帧 → ChatSSEEvent（api.md 5b 事件表）
    nonisolated private static func mapChatEvent(_ frame: SSEFrame) -> ChatSSEEvent? {
        struct IdPayload: Decodable { let id: Int64 }
        struct TextPayload: Decodable { let text: String }
        struct ChunkPayload: Decodable { let seq: Int; let base64: String }
        struct EndPayload: Decodable { let duration: String?; let url: String? }
        struct UserEnPayload: Decodable { let en: String; let raw: String }
        struct ErrorPayload: Decodable { let code: Int; let message: String }

        switch frame.event {
        case "reply_start":
            guard let p = frame.payload(IdPayload.self) else { return nil }
            return .replyStart(id: p.id)
        case "reply_delta":
            guard let p = frame.payload(TextPayload.self) else { return nil }
            return .replyDelta(text: p.text)
        case "reply_audio_chunk":
            guard let p = frame.payload(ChunkPayload.self),
                  let pcm = Data(base64Encoded: p.base64) else { return nil }
            return .replyAudioChunk(seq: p.seq, pcm: pcm)
        case "reply_end":
            let p = frame.payload(EndPayload.self)
            return .replyEnd(duration: p?.duration, url: p?.url)
        case "user_en":
            guard let p = frame.payload(UserEnPayload.self) else { return nil }
            return .userEn(en: p.en, raw: p.raw)
        case "user_audio_chunk":
            guard let p = frame.payload(ChunkPayload.self),
                  let pcm = Data(base64Encoded: p.base64) else { return nil }
            return .userAudioChunk(seq: p.seq, pcm: pcm)
        case "user_bubble":
            guard let p = frame.payload(UserBubblePayload.self) else { return nil }
            return .userBubble(p)
        case "error":
            guard let p = frame.payload(ErrorPayload.self) else { return nil }
            return .error(code: p.code, message: p.message)
        case "done":
            return .done
        default:
            return nil
        }
    }

    /// 接口 18：清空聊天记录
    func clearMessages(contactId: String) async throws -> Int {
        struct RemovedData: Decodable { let removed: Int }
        let data: RemovedData = try await http.delete(apiURL("/chats/\(contactId)/messages"))
        return data.removed
    }

    /// 接口 19：消息中文翻译（按需生成，服务端幂等）
    func translateMessage(id: Int64) async throws -> String {
        struct ZhData: Decodable { let zh: String }
        let data: ZhData = try await http.post(apiURL("/messages/\(id)/translate"))
        return data.zh
    }

    // MARK: - 辅助卡片（M3）

    /// 接口 16：中文语音 → zh/en/TTS 分片 SSE 流（TTS 失败下发 error 不降级）
    func assistTranslate(wav: Data) -> AsyncThrowingStream<AssistSSEEvent, Error> {
        do {
            let url = try apiURL("/assist/translate")
            var multipart = MultipartBody()
            multipart.addFile(name: "audio", filename: "assist.wav",
                              mimeType: "audio/wav", data: wav)
            return postSSE(url: url, multipart: multipart, map: Self.mapAssistEvent) {
                if case .done = $0 { return true }
                return false
            }
        } catch {
            return AsyncThrowingStream { $0.finish(throwing: error) }
        }
    }

    /// SSE 帧 → AssistSSEEvent（api.md 16 事件表）
    nonisolated private static func mapAssistEvent(_ frame: SSEFrame) -> AssistSSEEvent? {
        struct ZhPayload: Decodable { let zh: String }
        struct EnPayload: Decodable { let en: String }
        struct ChunkPayload: Decodable { let seq: Int; let base64: String }
        struct EndPayload: Decodable { let url: String; let duration: String }
        struct ErrorPayload: Decodable { let code: Int; let message: String }

        switch frame.event {
        case "zh":
            guard let p = frame.payload(ZhPayload.self) else { return nil }
            return .zh(p.zh)
        case "en":
            guard let p = frame.payload(EnPayload.self) else { return nil }
            return .en(p.en)
        case "audio_chunk":
            guard let p = frame.payload(ChunkPayload.self),
                  let pcm = Data(base64Encoded: p.base64) else { return nil }
            return .audioChunk(seq: p.seq, pcm: pcm)
        case "audio_end":
            guard let p = frame.payload(EndPayload.self) else { return nil }
            return .audioEnd(url: p.url, duration: p.duration)
        case "error":
            guard let p = frame.payload(ErrorPayload.self) else { return nil }
            return .error(code: p.code, message: p.message)
        case "done":
            return .done
        default:
            return nil
        }
    }

    /// 接口 17：复读语义校验（multipart 同步 JSON：{consistent, reason?}）
    func assistVerify(wav: Data, en: String) async throws -> VerifyResult {
        let url = try apiURL("/assist/verify")
        var multipart = MultipartBody()
        multipart.addFile(name: "audio", filename: "verify.wav",
                          mimeType: "audio/wav", data: wav)
        multipart.addField(name: "en", value: en)

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue(multipart.contentType, forHTTPHeaderField: "Content-Type")
        request.httpBody = multipart.finalized()

        let data: Data
        do {
            (data, _) = try await URLSession.shared.data(for: request)
        } catch {
            throw APIError.network(error)
        }
        return try HTTPClient.decodeEnvelope(data)
    }

    // MARK: - 基础数据

    /// 接口 3：联系人列表
    func fetchContacts() async throws -> [Contact] {
        try await http.get(apiURL("/contacts"))
    }
}

/// 建流前错误体解包裹用空载荷（泛型闭包内不能嵌套定义类型）
private struct EmptyPayload: Decodable {}

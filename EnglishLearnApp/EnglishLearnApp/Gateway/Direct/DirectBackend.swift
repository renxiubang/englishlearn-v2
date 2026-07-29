import Foundation

/// 直连通道桩（架构文档 §3.3，M4 里程碑实现）：
/// 后端不可达时 App 直连 dashscope qwen3-omni-flash，
/// DirectMLLMClient 三处差异适配 + DirectOrchestrator 两阶段编排 + CloudTTSClient。
@MainActor
final class DirectBackend: ChatBackend {
    private let settings: AppSettings

    init(settings: AppSettings) {
        self.settings = settings
    }

    func fetchMessages(contactId: String, cursor: Int64?, limit: Int) async throws -> MessagePage {
        throw APIError.notImplemented("M4")
    }

    func sendText(contactId: String, text: String) async throws -> ChatReply {
        throw APIError.notImplemented("M4")
    }

    func sendVoice(contactId: String, wav: Data) -> AsyncThrowingStream<ChatSSEEvent, Error> {
        AsyncThrowingStream { continuation in
            continuation.finish(throwing: APIError.notImplemented("M4"))
        }
    }

    func clearMessages(contactId: String) async throws -> Int {
        throw APIError.notImplemented("M4")
    }

    func translateMessage(id: Int64) async throws -> String {
        throw APIError.notImplemented("M4")
    }

    func assistTranslate(wav: Data) -> AsyncThrowingStream<AssistSSEEvent, Error> {
        AsyncThrowingStream { continuation in
            continuation.finish(throwing: APIError.notImplemented("M4"))
        }
    }

    func assistVerify(wav: Data, en: String) async throws -> VerifyResult {
        throw APIError.notImplemented("M4")
    }

    func fetchContacts() async throws -> [Contact] {
        throw APIError.notImplemented("M4")
    }
}

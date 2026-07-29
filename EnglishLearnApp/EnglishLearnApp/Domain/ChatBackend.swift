import Foundation

/// 领域层统一协议（架构文档 §3.1）：UI 只面向协议编程，
/// RemoteBackend（在线）/ DirectBackend（直连）由 BackendRouter 按可达性选择，
/// 两个实现产出同一套事件流，ChatView 消费逻辑与通道无关。
@MainActor
protocol ChatBackend {
    // 聊天（对应 api.md 4 / 5a / 5b / 18 / 19）
    func fetchMessages(contactId: String, cursor: Int64?, limit: Int) async throws -> MessagePage
    func sendText(contactId: String, text: String) async throws -> ChatReply
    func sendVoice(contactId: String, wav: Data) -> AsyncThrowingStream<ChatSSEEvent, Error>
    func clearMessages(contactId: String) async throws -> Int
    func translateMessage(id: Int64) async throws -> String
    // 辅助卡片（16 / 17）
    func assistTranslate(wav: Data) -> AsyncThrowingStream<AssistSSEEvent, Error>
    func assistVerify(wav: Data, en: String) async throws -> VerifyResult
    // 基础数据（3；1/2/9-15 随 M3/M6 扩展）
    func fetchContacts() async throws -> [Contact]
}

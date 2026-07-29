import Foundation

// MARK: - 通用（api.md 通用约定）

/// 统一响应包裹 `{ code, data, message }`
struct ApiResponse<T: Decodable>: Decodable {
    let code: Int
    let data: T?
    let message: String
}

/// 业务/网络错误，code 语义对齐 api.md 错误码汇总（400/404/409/413/429/500）
enum APIError: LocalizedError {
    case business(code: Int, message: String)
    case network(Error)
    case invalidResponse
    case notImplemented(String)

    var errorDescription: String? {
        switch self {
        case .business(let code, let message):
            switch code {
            case 409: return "AI 正在回复中，请稍候"
            case 429: return "操作太频繁，请稍后再试"
            default: return message.isEmpty ? "请求失败（\(code)）" : message
            }
        case .network: return "网络连接失败，请检查后端服务"
        case .invalidResponse: return "服务响应异常"
        case .notImplemented(let milestone): return "该功能将在 \(milestone) 里程碑提供"
        }
    }
}

// MARK: - 用户（接口 1 / 2）

struct UserProfile: Codable {
    let id: String
    let name: String
    let avatar: String
    let level: Int
    let levelTitle: String
    let totalHours: Int
}

struct UserStats: Codable {
    let todayMinutes: Int
    let streakDays: Int
}

// MARK: - 联系人（接口 3）

struct Contact: Codable, Identifiable, Hashable {
    let id: String
    let type: String          // "human" | "ai"
    let name: String
    let tag: String?
    let avatar: String?
    let emoji: String?
    let avatarBg: String?
    let sub: String
}

// MARK: - 聊天（接口 4 / 5 / 18 / 19）

/// 音频资源引用（后端 /audio/*.wav 或本地文件相对路径）
struct AudioRef: Codable, Hashable {
    let url: String
    let duration: String
}

struct ChatMessage: Codable, Identifiable, Hashable {
    /// 服务端主键；本地临时/离线消息为负数（对齐 Web 端临时气泡负 id 约定）
    var id: Int64
    var from: String           // "them" | "me"
    var en: String
    /// 中文经接口 19 按需生成，未翻译时为空串
    var zh: String
    /// me 语音消息原始逐字转录（原译，en 为 AI译）
    var raw: String?
    var duration: String?
    var score: Int?
    var textOnly: Bool?
    var userAudio: AudioRef?
    var ttsAudio: AudioRef?
    /// them 消息 AI 回复 TTS 音频
    var url: String?

    // 服务端可缺省 zh（历史契约为空串），容错解码
    enum CodingKeys: String, CodingKey {
        case id, from, en, zh, raw, duration, score, textOnly, userAudio, ttsAudio, url
    }

    init(id: Int64, from: String, en: String, zh: String = "", raw: String? = nil,
         duration: String? = nil, score: Int? = nil, textOnly: Bool? = nil,
         userAudio: AudioRef? = nil, ttsAudio: AudioRef? = nil, url: String? = nil) {
        self.id = id
        self.from = from
        self.en = en
        self.zh = zh
        self.raw = raw
        self.duration = duration
        self.score = score
        self.textOnly = textOnly
        self.userAudio = userAudio
        self.ttsAudio = ttsAudio
        self.url = url
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int64.self, forKey: .id)
        from = try c.decode(String.self, forKey: .from)
        en = try c.decode(String.self, forKey: .en)
        zh = try c.decodeIfPresent(String.self, forKey: .zh) ?? ""
        raw = try c.decodeIfPresent(String.self, forKey: .raw)
        duration = try c.decodeIfPresent(String.self, forKey: .duration)
        score = try c.decodeIfPresent(Int.self, forKey: .score)
        textOnly = try c.decodeIfPresent(Bool.self, forKey: .textOnly)
        userAudio = try c.decodeIfPresent(AudioRef.self, forKey: .userAudio)
        ttsAudio = try c.decodeIfPresent(AudioRef.self, forKey: .ttsAudio)
        url = try c.decodeIfPresent(String.self, forKey: .url)
    }
}

/// 接口 4：游标分页包装
struct MessagePage: Codable {
    let list: [ChatMessage]
    let hasMore: Bool
    let nextCursor: Int64?
}

/// 接口 5a 响应 data.reply
struct ChatReply: Codable {
    let id: Int64
    let from: String
    let en: String
    let zh: String?
    let duration: String?
    let textOnly: Bool?
}

// MARK: - SSE 事件（接口 5b / 16，M2 消费）

/// 接口 5b 事件表一一对应；pcm 为 base64 解码后的 Int16 PCM mono 24kHz 裸流
enum ChatSSEEvent {
    case replyStart(id: Int64)
    case replyDelta(text: String)
    case replyAudioChunk(seq: Int, pcm: Data)
    case replyEnd(duration: String?, url: String?)
    case userEn(en: String, raw: String)
    case userAudioChunk(seq: Int, pcm: Data)
    case userBubble(UserBubblePayload)
    case error(code: Int, message: String)
    case done
}

struct UserBubblePayload: Codable {
    let id: Int64
    let en: String
    let raw: String
    let userAudio: AudioRef
    /// TTS 降级时为 null（保文本）
    let ttsAudio: AudioRef?
}

/// 接口 16 事件表一一对应
enum AssistSSEEvent {
    case zh(String)
    case en(String)
    case audioChunk(seq: Int, pcm: Data)
    case audioEnd(url: String, duration: String)
    case error(code: Int, message: String)
    case done
}

/// 接口 17：复读语义校验结果
struct VerifyResult: Codable {
    let consistent: Bool
    let reason: String?
}

// MARK: - 收藏（接口 9 / 10 / 11）

struct Favorite: Codable, Identifiable, Hashable {
    let id: Int64
    let en: String
    let zh: String
    let createdAt: Int64
}

// MARK: - 看图讲故事（接口 12-15）

struct PicStory: Codable, Hashable {
    let title: String
    let seed: String
    let cat: String
    let sentences: [String]
}

typealias PicStoryProgress = [String: Int]

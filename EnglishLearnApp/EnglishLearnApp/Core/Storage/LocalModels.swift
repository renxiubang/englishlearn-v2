import Foundation
import SwiftData

// SwiftData 模型：镜像后端表结构（架构文档 §4.1）。
// 注：#Index 宏需 iOS 18+，当前部署目标 17.0，热点查询暂靠 fetchLimit + 谓词；升级后补
// #Index<LocalMessage>([\.contactId, \.localId])（对齐后端 idx_timeline）。

/// 镜像 contacts（接口 3）
@Model
final class LocalContact {
    @Attribute(.unique) var id: String
    var type: String            // human / ai
    var name: String
    var tag: String?
    var avatar: String?
    var emoji: String?
    var avatarBg: String?
    var sub: String
    /// 直连模式对话用；来源为 App 内置 seed（后端不外泄，架构文档 §3.3）
    var personaPrompt: String
    var sortOrder: Int
    var createdAt: Date
    var updatedAt: Date

    init(id: String, type: String, name: String, tag: String? = nil, avatar: String? = nil,
         emoji: String? = nil, avatarBg: String? = nil, sub: String = "",
         personaPrompt: String = "", sortOrder: Int = 0) {
        self.id = id
        self.type = type
        self.name = name
        self.tag = tag
        self.avatar = avatar
        self.emoji = emoji
        self.avatarBg = avatarBg
        self.sub = sub
        self.personaPrompt = personaPrompt
        self.sortOrder = sortOrder
        self.createdAt = Date()
        self.updatedAt = Date()
    }
}

/// 镜像 messages（接口 4/5/19）
@Model
final class LocalMessage {
    /// 本地主键；在线消息直接等于服务端 id，离线产生取负数递减
    @Attribute(.unique) var localId: Int64
    /// 服务端消息 id（同步成功后回写）
    var serverId: Int64?
    var contactId: String
    var fromSide: String        // them / me
    var en: String
    var zh: String              // 按需生成（接口 19），未翻译为空串
    var raw: String?            // 原译（me 语音消息）
    var duration: String?       // "m:ss"；nil = 纯文本
    var score: Int?
    var textOnly: Bool
    /// 本地音频相对路径（§4.2）；未缓存时存远端 URL
    var userAudioPath: String?
    var userAudioDuration: String?
    var ttsAudioPath: String?
    var ttsAudioDuration: String?
    /// synced / pendingUpload / uploading / failed（§4.4 状态机）
    var syncState: String
    var createdAt: Date
    var updatedAt: Date

    init(localId: Int64, serverId: Int64?, contactId: String, fromSide: String,
         en: String, zh: String = "", raw: String? = nil, duration: String? = nil,
         score: Int? = nil, textOnly: Bool = false,
         userAudioPath: String? = nil, userAudioDuration: String? = nil,
         ttsAudioPath: String? = nil, ttsAudioDuration: String? = nil,
         syncState: String = "synced", createdAt: Date = Date()) {
        self.localId = localId
        self.serverId = serverId
        self.contactId = contactId
        self.fromSide = fromSide
        self.en = en
        self.zh = zh
        self.raw = raw
        self.duration = duration
        self.score = score
        self.textOnly = textOnly
        self.userAudioPath = userAudioPath
        self.userAudioDuration = userAudioDuration
        self.ttsAudioPath = ttsAudioPath
        self.ttsAudioDuration = ttsAudioDuration
        self.syncState = syncState
        self.createdAt = createdAt
        self.updatedAt = Date()
    }
}

/// 镜像 favorites（接口 9/10/11，M3 使用）
@Model
final class LocalFavorite {
    @Attribute(.unique) var localId: Int64
    var serverId: Int64?
    /// 英文原句（会话内唯一去重键）
    var en: String
    var zh: String
    /// synced / pendingUpload / uploading / failed / pendingDelete
    var syncState: String
    var createdAt: Date

    init(localId: Int64, serverId: Int64?, en: String, zh: String = "",
         syncState: String = "synced", createdAt: Date = Date()) {
        self.localId = localId
        self.serverId = serverId
        self.en = en
        self.zh = zh
        self.syncState = syncState
        self.createdAt = createdAt
    }
}

/// 镜像 pic_story_progress（接口 14/15，M6 使用）
@Model
final class LocalPicStoryProgress {
    @Attribute(.unique) var seed: String
    /// 本地也执行"只保最高分"（对齐服务端 GREATEST 语义）
    var bestScore: Int
    var syncState: String

    init(seed: String, bestScore: Int, syncState: String = "synced") {
        self.seed = seed
        self.bestScore = bestScore
        self.syncState = syncState
    }
}

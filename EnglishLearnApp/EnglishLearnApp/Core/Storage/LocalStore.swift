import Foundation
import Observation
import SwiftData

/// 本地镜像仓储（架构文档 §4.3 本地优先读写路径）：
/// 页面一律先查本地渲染，在线拉取后 upsert 覆盖镜像。
@MainActor
@Observable
final class LocalStore {
    let container: ModelContainer
    private var context: ModelContext { container.mainContext }

    init() {
        let schema = Schema([
            LocalContact.self, LocalMessage.self,
            LocalFavorite.self, LocalPicStoryProgress.self,
        ])
        do {
            container = try ModelContainer(for: schema)
        } catch {
            // 模型变更导致的不兼容（开发期）：重建容器，本地为镜像缓存可安全丢弃
            container = try! ModelContainer(
                for: schema,
                configurations: ModelConfiguration(isStoredInMemoryOnly: true)
            )
        }
    }

    // MARK: - 联系人

    func loadContacts() -> [Contact] {
        let descriptor = FetchDescriptor<LocalContact>(sortBy: [SortDescriptor(\.sortOrder)])
        let rows = (try? context.fetch(descriptor)) ?? []
        return rows.map {
            Contact(id: $0.id, type: $0.type, name: $0.name, tag: $0.tag,
                    avatar: $0.avatar, emoji: $0.emoji, avatarBg: $0.avatarBg, sub: $0.sub)
        }
    }

    /// 在线拉取覆盖镜像：仅更新展示字段，persona 以内置 seed 为准（架构文档 §3.3）
    func upsertContacts(_ contacts: [Contact]) {
        for (index, c) in contacts.enumerated() {
            if let row = fetchContact(id: c.id) {
                row.type = c.type
                row.name = c.name
                row.tag = c.tag
                row.avatar = c.avatar
                row.emoji = c.emoji
                row.avatarBg = c.avatarBg
                row.sub = c.sub
                row.sortOrder = index
                row.updatedAt = Date()
            } else {
                context.insert(LocalContact(
                    id: c.id, type: c.type, name: c.name, tag: c.tag, avatar: c.avatar,
                    emoji: c.emoji, avatarBg: c.avatarBg, sub: c.sub, sortOrder: index))
            }
        }
        try? context.save()
    }

    /// 首启内置 seed 兜底（含 persona，直连模式对话用）
    func seedBuiltinContactsIfNeeded() {
        guard loadContacts().isEmpty else { return }
        for seed in BuiltinSeed.load() {
            context.insert(LocalContact(
                id: seed.id, type: seed.type, name: seed.name, tag: seed.tag,
                avatar: seed.avatar, emoji: seed.emoji, avatarBg: seed.avatarBg,
                sub: seed.sub, personaPrompt: seed.personaPrompt, sortOrder: seed.sortOrder))
        }
        try? context.save()
    }

    func personaPrompt(contactId: String) -> String {
        fetchContact(id: contactId)?.personaPrompt ?? ""
    }

    private func fetchContact(id: String) -> LocalContact? {
        var descriptor = FetchDescriptor<LocalContact>(predicate: #Predicate { $0.id == id })
        descriptor.fetchLimit = 1
        return try? context.fetch(descriptor).first
    }

    // MARK: - 消息

    /// 本地最近一页（createdAt 正序返回，供进聊天页秒开）
    func loadRecentMessages(contactId: String, limit: Int = 20) -> [ChatMessage] {
        var descriptor = FetchDescriptor<LocalMessage>(
            predicate: #Predicate { $0.contactId == contactId },
            sortBy: [SortDescriptor(\.createdAt, order: .reverse), SortDescriptor(\.localId, order: .reverse)]
        )
        descriptor.fetchLimit = limit
        let rows = (try? context.fetch(descriptor)) ?? []
        return rows.reversed().map { $0.toDTO() }
    }

    /// 在线数据写镜像（syncState=synced，serverId 即 localId）
    func upsertServerMessages(contactId: String, _ messages: [ChatMessage]) {
        for m in messages {
            let sid = m.id
            var descriptor = FetchDescriptor<LocalMessage>(
                predicate: #Predicate { $0.contactId == contactId && $0.serverId == sid })
            descriptor.fetchLimit = 1
            if let row = try? context.fetch(descriptor).first {
                row.en = m.en
                if !m.zh.isEmpty { row.zh = m.zh }
                row.raw = m.raw
                row.duration = m.duration
                row.score = m.score
                row.textOnly = m.textOnly ?? false
                row.updatedAt = Date()
            } else {
                context.insert(LocalMessage(
                    localId: sid, serverId: sid, contactId: contactId, fromSide: m.from,
                    en: m.en, zh: m.zh, raw: m.raw, duration: m.duration, score: m.score,
                    textOnly: m.textOnly ?? false,
                    userAudioPath: m.userAudio?.url, userAudioDuration: m.userAudio?.duration,
                    ttsAudioPath: m.from == "them" ? m.url : m.ttsAudio?.url,
                    ttsAudioDuration: m.ttsAudio?.duration))
            }
        }
        try? context.save()
    }

    /// 接口 19 译文写回（幂等）
    func setZh(contactId: String, serverId: Int64, zh: String) {
        var descriptor = FetchDescriptor<LocalMessage>(
            predicate: #Predicate { $0.contactId == contactId && $0.serverId == serverId })
        descriptor.fetchLimit = 1
        guard let row = try? context.fetch(descriptor).first else { return }
        row.zh = zh
        row.updatedAt = Date()
        try? context.save()
    }

    /// 接口 18 清空：删除会话全部本地消息
    func clearMessages(contactId: String) {
        try? context.delete(model: LocalMessage.self,
                            where: #Predicate { $0.contactId == contactId })
        try? context.save()
    }
}

// MARK: - DTO 映射

private extension LocalMessage {
    func toDTO() -> ChatMessage {
        var userAudio: AudioRef?
        if let path = userAudioPath, let dur = userAudioDuration {
            userAudio = AudioRef(url: path, duration: dur)
        }
        var ttsAudio: AudioRef?
        if fromSide == "me", let path = ttsAudioPath, let dur = ttsAudioDuration {
            ttsAudio = AudioRef(url: path, duration: dur)
        }
        return ChatMessage(
            id: serverId ?? localId, from: fromSide, en: en, zh: zh, raw: raw,
            duration: duration, score: score, textOnly: textOnly ? true : nil,
            userAudio: userAudio, ttsAudio: ttsAudio,
            url: fromSide == "them" ? ttsAudioPath : nil)
    }
}

// MARK: - 内置联系人 seed（Resources/BuiltinContacts.json，与 backend/seeds/seed.py 同源维护）

struct BuiltinSeed: Decodable {
    let id: String
    let type: String
    let name: String
    let tag: String?
    let avatar: String?
    let emoji: String?
    let avatarBg: String?
    let sub: String
    let personaPrompt: String
    let sortOrder: Int

    static func load() -> [BuiltinSeed] {
        guard let url = Bundle.main.url(forResource: "BuiltinContacts", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let seeds = try? JSONDecoder().decode([BuiltinSeed].self, from: data) else {
            return []
        }
        return seeds
    }
}

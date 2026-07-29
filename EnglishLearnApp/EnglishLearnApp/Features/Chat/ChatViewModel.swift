import Foundation
import Observation

/// 聊天页视图模型（M1：接口 4/5a/18/19；M2：5b 语音链路；M3：16/17 辅助卡片）
@MainActor
@Observable
final class ChatViewModel {
    let contact: Contact

    private(set) var messages: [ChatMessage] = []
    private(set) var hasMore = false
    private(set) var nextCursor: Int64?
    private(set) var sending = false
    private(set) var loadingEarlier = false
    var errorText: String?
    /// 短提示（录音太短/语种降级等，对齐 Web 端 toast）
    var hintText: String?

    private let router: BackendRouter
    private let store: LocalStore
    private let settings: AppSettings
    /// 乐观上屏临时气泡负 id（对齐 Web 端约定）
    private var tempId: Int64 = -1
    /// M2 语音链路
    private let recorder = Recorder()
    private let pcmPlayer = PcmStreamPlayer()

    init(contact: Contact, router: BackendRouter, store: LocalStore, settings: AppSettings) {
        self.contact = contact
        self.router = router
        self.store = store
        self.settings = settings
    }

    var isOnline: Bool { router.channel == .online }

    /// 进入聊天页：先展示本地最近一页，后台调接口 4 对账刷新（架构文档 §4.3）
    func load() async {
        if messages.isEmpty {
            messages = store.loadRecentMessages(contactId: contact.id)
        }
        await router.refresh()
        guard isOnline else { return }
        do {
            let page = try await router.backend.fetchMessages(
                contactId: contact.id, cursor: nil, limit: 20)
            messages = page.list
            hasMore = page.hasMore
            nextCursor = page.nextCursor
            store.upsertServerMessages(contactId: contact.id, page.list)
        } catch {
            errorText = error.localizedDescription
        }
    }

    /// 上滑到顶加载更早一页，前插到列表头部
    func loadEarlier() async {
        guard isOnline, hasMore, let cursor = nextCursor, !loadingEarlier else { return }
        loadingEarlier = true
        defer { loadingEarlier = false }
        do {
            let page = try await router.backend.fetchMessages(
                contactId: contact.id, cursor: cursor, limit: 20)
            messages.insert(contentsOf: page.list, at: 0)
            hasMore = page.hasMore
            nextCursor = page.nextCursor
            store.upsertServerMessages(contactId: contact.id, page.list)
        } catch {
            errorText = error.localizedDescription
        }
    }

    /// 接口 5a：文本消息。我方气泡乐观上屏，回复到达后拉最新页与服务端对账
    /// （5a 不返回我方消息 id，以服务端为准重建，避免本地负 id 长期悬挂）
    func sendText(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !sending else { return }
        guard isOnline else {
            errorText = "当前离线，文本对话将在 M4 直连里程碑支持"
            return
        }
        sending = true
        defer { sending = false }

        let placeholder = ChatMessage(id: tempId, from: "me", en: trimmed, textOnly: true)
        tempId -= 1
        messages.append(placeholder)
        do {
            let reply = try await router.backend.sendText(contactId: contact.id, text: trimmed)
            messages.append(ChatMessage(
                id: reply.id, from: reply.from, en: reply.en, zh: reply.zh ?? "",
                duration: reply.duration, textOnly: reply.textOnly))
            // 后台对账：拉最新页替换（获得我方消息真实 id 并落镜像）
            if let page = try? await router.backend.fetchMessages(
                contactId: contact.id, cursor: nil, limit: 20) {
                messages = page.list
                hasMore = page.hasMore
                nextCursor = page.nextCursor
                store.upsertServerMessages(contactId: contact.id, page.list)
            }
        } catch {
            messages.removeAll { $0.id == placeholder.id }
            errorText = error.localizedDescription
        }
    }

    /// 接口 19：点击「翻译」按需生成中文（服务端幂等，写回镜像）
    func translate(_ message: ChatMessage) async {
        guard message.id > 0, message.zh.isEmpty else { return }
        guard isOnline else {
            errorText = "当前离线，翻译将在 M4 直连里程碑支持"
            return
        }
        do {
            let zh = try await router.backend.translateMessage(id: message.id)
            if let index = messages.firstIndex(where: { $0.id == message.id }) {
                messages[index].zh = zh
            }
            store.setZh(contactId: contact.id, serverId: message.id, zh: zh)
        } catch {
            errorText = error.localizedDescription
        }
    }

    /// 接口 18：清空聊天记录（含本地镜像）
    func clearAll() async {
        guard isOnline else {
            errorText = "当前离线，无法清空服务端记录"
            return
        }
        do {
            _ = try await router.backend.clearMessages(contactId: contact.id)
            store.clearMessages(contactId: contact.id)
            messages = []
            hasMore = false
            nextCursor = nil
        } catch {
            errorText = error.localizedDescription
        }
    }

    // MARK: - M2 语音链路（对应 Web ChatView.vue onTalkStart/onTalkCancel/onTalkSend）

    /// 按住：预加载语种模型 + 停掉流播 + 开始录音
    func startTalk() async {
        LangDetector.shared.preload()
        pcmPlayer.stop()
        FilePlayer.shared.stop()
        // 跟读录音期间抑制后续分片续播（feed 会切回播放会话打断采集）
        if assistShown {
            suppressAssistAudio = true
            assistPlaying = false
        }
        if await !recorder.start() {
            hintText = "无法访问麦克风，请检查权限"
        }
        recorder.onLimit = { [weak self] in self?.hintText = "录音已达 60 秒上限" }
    }

    /// 上滑取消：丢弃录音
    func cancelTalk() {
        recorder.cancel()
    }

    /// 松开发送：长度校验 → 跟读/语种分流 → 英文走 5b，中文开辅助卡片（对齐 Web onTalkSend）
    func finishTalk() async {
        guard let rec = recorder.stop() else { return }
        guard rec.seconds >= 0.5 else {
            hintText = "说话时间太短"
            return
        }
        // 辅助卡片已打开：松开 = 记录一段跟读语音
        if assistShown {
            assistRecordings.append(rec)
            verifyError = ""
            hintText = "已记录跟读语音，可继续跟读或点击「读完啦」"
            return
        }
        guard !sending else {
            hintText = "AI 正在回复中，请稍候"
            return
        }
        guard isOnline else {
            errorText = "当前离线，语音对话将在 M4 直连里程碑支持"
            return
        }
        let lang = LangDetector.shared.detect(samples: rec.samples)
        if LangDetector.shared.warnedFallback {
            hintText = "语种模型加载失败，暂按英文处理"
        }
        if lang == "zh" {
            // 识别到中文 → 进入辅助卡片（接口 16）
            hintText = "识别到中文，正在为你进入辅助…"
            startAssist(rec)
            return
        }
        await sendVoice(rec)
    }

    /// 接口 5b：上传语音 → 消费 SSE（AI 回复流式 + 用户气泡回填，对齐 Web sendVoice）
    private func sendVoice(_ rec: Recorder.Recording) async {
        sending = true
        defer { sending = false }

        let pendingId = tempId
        tempId -= 1
        messages.append(ChatMessage(
            id: pendingId, from: "me", en: "", duration: Self.fmtSeconds(rec.seconds)))
        var aiId: Int64?

        do {
            for try await event in router.backend.sendVoice(contactId: contact.id, wav: rec.wav) {
                switch event {
                case .replyStart(let id):
                    aiId = id
                    messages.append(ChatMessage(id: id, from: "them", en: ""))
                case .replyDelta(let text):
                    if let index = index(of: aiId) { messages[index].en += text }
                case .replyAudioChunk(_, let pcm):
                    pcmPlayer.feed(pcm)   // 边收边播
                case .replyEnd(let duration, let url):
                    if let index = index(of: aiId) {
                        messages[index].duration = duration
                        messages[index].url = url
                    }
                case .userEn(let en, let raw):
                    if let index = index(of: pendingId) {
                        messages[index].en = en
                        messages[index].raw = raw
                    }
                case .userAudioChunk:
                    break   // 自己消息的合成音不当场播放（对齐 Web），终态 URL 供回放
                case .userBubble(let payload):
                    if let index = index(of: pendingId) {
                        messages[index] = ChatMessage(
                            id: payload.id, from: "me", en: payload.en, raw: payload.raw,
                            duration: payload.userAudio.duration,
                            userAudio: payload.userAudio, ttsAudio: payload.ttsAudio)
                    }
                case .error(_, let message):
                    throw APIError.business(code: 500, message: message)
                case .done:
                    break
                }
            }
            // 对账：拉最新页落镜像（获得权威数据，含双方音频 URL）
            if let page = try? await router.backend.fetchMessages(
                contactId: contact.id, cursor: nil, limit: 20) {
                messages = page.list
                hasMore = page.hasMore
                nextCursor = page.nextCursor
                store.upsertServerMessages(contactId: contact.id, page.list)
            }
        } catch {
            // 失败回滚：移除 pending 气泡与半成品 AI 气泡（架构文档 §7.2）
            pcmPlayer.stop()
            messages.removeAll { $0.id == pendingId || $0.id == aiId }
            errorText = error.localizedDescription
        }
    }

    private func index(of id: Int64?) -> Int? {
        guard let id else { return nil }
        return messages.firstIndex { $0.id == id }
    }

    // MARK: - M3 辅助卡片（接口 16/17，对应 Web AssistCard.vue + ChatView.onAssistFinish）

    private(set) var assistShown = false
    private(set) var assistZh = ""
    private(set) var assistEn = ""
    /// 接口 16 audio_end 后的完整 wav（未就绪时点击语音条不重播，等分片自动播）
    private(set) var assistTtsUrl: String?
    private(set) var assistTtsDuration = ""
    private(set) var assistPlaying = false
    /// 跟读录音段（松手一次追加一段，只回放/删除最后一段）
    private(set) var assistRecordings: [Recorder.Recording] = []
    private(set) var assistVoicePlaying = false
    /// 接口 17 校验进行中（「读完啦」置灰 + 口音比对中提示）
    private(set) var verifying = false
    /// 校验不通过原因（录音清空后在语音位置就地展示）
    private(set) var verifyError = ""
    private var assistTask: Task<Void, Never>?
    /// 跟读录音期间丢弃后续流式分片（feed 会激活播放会话，打断 playAndRecord 采集）
    private var suppressAssistAudio = false

    /// 跟读段总时长文案（对齐 Web voiceDur）
    var assistVoiceDuration: String {
        Self.fmtSeconds(assistRecordings.reduce(0) { $0 + $1.seconds })
    }

    /// 接口 16：中文录音 → 卡片流式填充 zh/en + TTS 分片边收边播
    func startAssist(_ rec: Recorder.Recording) {
        closeAssist()
        assistShown = true
        assistTask = Task {
            do {
                for try await event in router.backend.assistTranslate(wav: rec.wav) {
                    switch event {
                    case .zh(let zh):
                        assistZh = zh
                    case .en(let en):
                        assistEn = en
                    case .audioChunk(_, let pcm):
                        if !suppressAssistAudio {
                            assistPlaying = true
                            pcmPlayer.feed(pcm)
                        }
                    case .audioEnd(let url, let duration):
                        assistTtsUrl = url
                        assistTtsDuration = duration
                        assistPlaying = false
                    case .error(_, let message):
                        // TTS 失败不降级（对齐接口 16）：文本保留，语音提示失败
                        assistPlaying = false
                        hintText = message
                    case .done:
                        break
                    }
                }
            } catch {
                if !Task.isCancelled {
                    assistPlaying = false
                    hintText = "辅助翻译失败：\(error.localizedDescription)"
                }
            }
        }
    }

    /// 合成语音条：播放中停止；wav 就绪后整段重播（对齐 Web togglePlay）
    func toggleAssistTts() {
        if assistPlaying {
            assistPlaying = false
            pcmPlayer.stop()
            FilePlayer.shared.stop()
            return
        }
        guard let url = assistTtsUrl else { return }   // 流式尚未就绪：等分片自动播放
        assistPlaying = true
        FilePlayer.shared.play(url: url, baseURL: settings.backendBaseURL) { [weak self] in
            self?.assistPlaying = false
        }
    }

    /// 跟读回放：播最后一段录音（对齐 Web playVoices）
    func playAssistVoice() {
        guard let last = assistRecordings.last, !assistVoicePlaying else { return }
        assistVoicePlaying = true
        FilePlayer.shared.play(data: last.wav) { [weak self] in
            self?.assistVoicePlaying = false
        }
    }

    /// 删除最后一段跟读录音
    func removeLastAssistVoice() {
        guard !assistRecordings.isEmpty else { return }
        assistRecordings.removeLast()
    }

    /// 「读完啦」：接口 17 复读校验；通过 → 关卡片 + 复读音频走 5b 正式发送；
    /// 不通过 → 清空录音 + 就地展示原因（对齐 Web onAssistFinish）
    func finishAssist() async {
        guard !verifying else { return }
        guard let rec = assistRecordings.last, !assistEn.isEmpty else {
            hintText = "请先跟读一遍"
            return
        }
        verifying = true
        verifyError = ""
        do {
            let result = try await router.backend.assistVerify(wav: rec.wav, en: assistEn)
            verifying = false
            guard result.consistent else {
                assistRecordings = []
                verifyError = result.reason ?? "读的不太准，重新来一次吧"
                return
            }
            closeAssist()
            await sendVoice(rec)
        } catch {
            verifying = false
            verifyError = error.localizedDescription
        }
    }

    /// 关闭卡片：取消流任务、停播放、重置全部辅助态
    func closeAssist() {
        assistTask?.cancel()
        assistTask = nil
        if assistShown {
            pcmPlayer.stop()
            FilePlayer.shared.stop()
        }
        assistShown = false
        assistZh = ""
        assistEn = ""
        assistTtsUrl = nil
        assistTtsDuration = ""
        assistPlaying = false
        assistVoicePlaying = false
        assistRecordings = []
        verifyError = ""
        suppressAssistAudio = false
    }

    /// 秒数 → "m:ss"（对齐 Web fmtSeconds）
    private static func fmtSeconds(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        return "\(total / 60):" + String(format: "%02d", total % 60)
    }
}

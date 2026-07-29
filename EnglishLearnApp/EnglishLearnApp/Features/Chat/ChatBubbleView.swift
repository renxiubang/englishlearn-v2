import SwiftUI

/// 聊天气泡（对应 Web ChatBubble.vue）：
/// 双方英文 + 按需翻译；me 语音消息展示原译/AI译（用户可见文案统一为「AI译」）；
/// M2：语音条点击回放（them=回复 TTS，me=用户原声）、them 慢速、me AI读
struct ChatBubbleView: View {
    let message: ChatMessage
    let contact: Contact
    let onTranslate: () -> Void

    @Environment(AppSettings.self) private var settings
    @State private var playing = false

    private var isMe: Bool { message.from == "me" }
    /// 语音条主播放音频（对齐 Web mainUrl：them=tts url，me=用户原声）
    private var mainURL: String? { isMe ? message.userAudio?.url : message.url }

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if isMe { Spacer(minLength: 48) }
            if !isMe {
                ContactAvatarView(contact: contact, size: 32)
            }
            bubble
            if !isMe { Spacer(minLength: 48) }
        }
        .frame(maxWidth: .infinity, alignment: isMe ? .trailing : .leading)
    }

    private var bubble: some View {
        VStack(alignment: .leading, spacing: 6) {
            // 语音条：点击播放/停止（历史语音消息 duration 非空；TTS 降级无音频时不可点）
            if let duration = message.duration, message.textOnly != true {
                Button {
                    togglePlay()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: playing ? "speaker.wave.3.fill" : "speaker.wave.2.fill")
                            .symbolEffect(.variableColor.iterative, isActive: playing)
                        Text(duration).font(.caption)
                    }
                }
                .buttonStyle(.plain)
                .disabled(mainURL == nil)
                // 无音频可播（种子消息/TTS 降级）时压淡，避免误以为可点
                .opacity(mainURL == nil ? 0.45 : 1)
                .foregroundStyle(isMe ? .white.opacity(0.9) : .secondary)
            }

            // me 语音消息：原译（逐字转录）+ AI译（语法修正英文）
            if isMe, let raw = message.raw, !raw.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    labeledText("原译", raw)
                    labeledText("AI译", message.en)
                }
            } else {
                Text(message.en)
                    .font(.body)
            }

            // 中文：接口 19 按需生成；未生成时展示「翻译」按钮
            if !message.zh.isEmpty {
                Divider()
                    .overlay(isMe ? Color.white.opacity(0.4) : Color.secondary.opacity(0.3))
                Text(message.zh)
                    .font(.subheadline)
                    .foregroundStyle(isMe ? .white.opacity(0.9) : .secondary)
            } else if message.id > 0 {
                Button(action: onTranslate) {
                    Label("翻译", systemImage: "character.book.closed")
                        .font(.caption)
                }
                .buttonStyle(.plain)
                .foregroundStyle(isMe ? .white.opacity(0.85) : Color.accentColor)
            }

            if let score = message.score {
                Text("评分 \(score)")
                    .font(.caption2)
                    .foregroundStyle(isMe ? .white.opacity(0.8) : .secondary)
            }

            // 辅助操作（对齐 Web 展开区）：them 慢速 / me AI读
            if message.textOnly != true {
                if !isMe, message.url != nil {
                    actionButton("慢速", icon: "tortoise") { play(message.url, rate: 0.7) }
                } else if isMe, let tts = message.ttsAudio?.url {
                    actionButton("AI读", icon: "waveform") { play(tts) }
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(
            isMe ? AnyShapeStyle(Color.accentColor) : AnyShapeStyle(.fill.secondary),
            in: RoundedRectangle(cornerRadius: 16))
        .foregroundStyle(isMe ? .white : .primary)
    }

    private func labeledText(_ label: String, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(isMe ? .white.opacity(0.7) : .secondary)
            Text(text)
                .font(.body)
        }
    }

    private func actionButton(_ title: String, icon: String,
                              action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(title, systemImage: icon)
                .font(.caption)
        }
        .buttonStyle(.plain)
        .foregroundStyle(isMe ? .white.opacity(0.85) : Color.accentColor)
    }

    // MARK: - 播放（FilePlayer 全局单例，新播放打断上一个）

    private func togglePlay() {
        if playing {
            FilePlayer.shared.stop()
            return
        }
        play(mainURL)
    }

    private func play(_ url: String?, rate: Float = 1) {
        guard let url else { return }
        playing = true
        FilePlayer.shared.play(url: url, baseURL: settings.backendBaseURL, rate: rate) {
            playing = false
        }
    }
}

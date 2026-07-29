import SwiftUI

/// 辅助卡片（对应 web/src/components/AssistCard.vue 的 chat 模式）：
/// 中文语音触发后流式展示中/英翻译与合成语音（分片边收边播、wav 就绪可重播），
/// 逐词点读、跟读语音条与「读完啦」校验；收藏星随收藏功能（接口 9/10/11）补充。
struct AssistCardView: View {
    let model: ChatViewModel

    /// 英文文本展开
    @State private var enShown = false
    /// 逐词点读高亮下标（1.2s 后复位）
    @State private var activeWord = -1

    private var words: [String] {
        model.assistEn.isEmpty ? [] : model.assistEn.split(separator: " ").map(String.init)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // 中文文本（流式回填前显示占位）
            Text(model.assistZh.isEmpty ? "正在翻译…" : model.assistZh)
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.trailing, 28)

            ttsRow

            if enShown, !words.isEmpty {
                enText
            }

            if !model.assistRecordings.isEmpty {
                voiceRow
            } else if !model.verifyError.isEmpty {
                // 校验不通过：录音已清空，在语音位置说明原因
                Text(model.verifyError)
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 12)
        .background(.background)
        .overlay(alignment: .topTrailing) {
            Button {
                model.closeAssist()
            } label: {
                Image(systemName: "xmark")
                    .font(.footnote)
                    .foregroundStyle(.tertiary)
                    .padding(10)
            }
        }
        .overlay(alignment: .top) { Divider() }
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    /// 合成语音条 + 查看英文文本按钮
    private var ttsRow: some View {
        HStack(spacing: 10) {
            Button {
                model.toggleAssistTts()
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: model.assistPlaying
                          ? "speaker.wave.3.fill" : "speaker.wave.2.fill")
                        .symbolEffect(.variableColor.iterative, isActive: model.assistPlaying)
                    if !model.assistTtsDuration.isEmpty {
                        Text(model.assistTtsDuration).font(.caption2)
                    }
                    Spacer(minLength: 0)
                }
                .font(.footnote)
                .foregroundStyle(Color.accentColor)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.accentColor.opacity(0.12),
                            in: RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.plain)

            Button {
                withAnimation(.easeOut(duration: 0.15)) { enShown.toggle() }
            } label: {
                Text(enShown ? "收起英文文本" : "点击查看英文文本")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Color.accentColor)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.fill.tertiary, in: Capsule())
            }
            .buttonStyle(.plain)
        }
        .padding(.trailing, 24)
    }

    /// 英文文本：逐词点读（高亮 + 短提示，对齐 Web playWord）
    private var enText: some View {
        FlowText(words: words, activeIndex: activeWord) { index in
            activeWord = index
            model.hintText = "🔊 " + words[index]
            Task {
                try? await Task.sleep(for: .seconds(1.2))
                if activeWord == index { activeWord = -1 }
            }
        }
    }

    /// 跟读语音条（播放/删除最后一段 + 计数徽标）+「读完啦」
    private var voiceRow: some View {
        HStack(alignment: .center, spacing: 8) {
            Button {
                model.playAssistVoice()
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: model.assistVoicePlaying
                          ? "speaker.wave.3.fill" : "speaker.wave.2.fill")
                        .symbolEffect(.variableColor.iterative,
                                      isActive: model.assistVoicePlaying)
                    Text(model.assistVoiceDuration).font(.caption2)
                }
                .font(.footnote)
                .foregroundStyle(.orange)
            }
            .buttonStyle(.plain)

            Button {
                model.removeLastAssistVoice()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.footnote)
                    .foregroundStyle(.tertiary)
            }
            .buttonStyle(.plain)

            if model.assistRecordings.count > 1 {
                Text("\(model.assistRecordings.count)")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(Color.accentColor, in: Capsule())
                Text("(每次删除最后一段)")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
            }

            Spacer(minLength: 8)

            VStack(alignment: .trailing, spacing: 4) {
                Button {
                    Task { await model.finishAssist() }
                } label: {
                    Text("读完啦")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(model.verifying ? Color.secondary : .white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 6)
                        .background(model.verifying
                                    ? AnyShapeStyle(.fill.tertiary)
                                    : AnyShapeStyle(Color.orange),
                                    in: Capsule())
                }
                .buttonStyle(.plain)
                .disabled(model.verifying)
                if model.verifying {
                    Text("口音比对中…")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

/// 逐词流式排版（点读高亮）：SwiftUI 无原生 flow layout 场景下用 Text 拼接 +
/// 词级点击退化为横向自动换行的 WrappingHStack 简化实现
private struct FlowText: View {
    let words: [String]
    let activeIndex: Int
    let onTap: (Int) -> Void

    var body: some View {
        // 用 FlowLayout 逐词排布，保证换行与词级点击
        FlowLayout(spacing: 4) {
            ForEach(Array(words.enumerated()), id: \.offset) { index, word in
                Text(word)
                    .font(.callout.weight(.semibold))
                    .padding(.horizontal, 2)
                    .padding(.vertical, 1)
                    .background(activeIndex == index
                                ? Color.accentColor.opacity(0.15) : .clear,
                                in: RoundedRectangle(cornerRadius: 4))
                    .foregroundStyle(activeIndex == index
                                     ? Color.accentColor : .primary)
                    .onTapGesture { onTap(index) }
            }
        }
    }
}

/// 简易流式布局（Layout 协议）：子视图按行排布，超宽换行
private struct FlowLayout: Layout {
    var spacing: CGFloat = 4

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: width == .infinity ? x : width, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize,
                       subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > bounds.minX, x + size.width > bounds.maxX {
                x = bounds.minX
                y += rowHeight + spacing
                rowHeight = 0
            }
            subview.place(at: CGPoint(x: x, y: y), anchor: .topLeading,
                          proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

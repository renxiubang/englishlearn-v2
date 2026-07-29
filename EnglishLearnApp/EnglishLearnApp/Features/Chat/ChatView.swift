import SwiftUI

/// 聊天页（对应 Web ChatView.vue：历史分页 + 文本对话 + 点译 + 清空 + 语音对话 + 辅助卡片）
struct ChatView: View {
    let contact: Contact

    @Environment(BackendRouter.self) private var router
    @Environment(LocalStore.self) private var store
    @Environment(AppSettings.self) private var settings
    @State private var model: ChatViewModel?
    @State private var draft = ""
    @State private var showClearConfirm = false
    /// 语音/文本输入模式（对应 Web 端 inputMode，语音模式显示「按住 说话」）
    @State private var voiceMode = false

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                ProgressView()
            }
        }
        .navigationTitle(contact.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) { ChannelBadge() }
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button(role: .destructive) {
                        showClearConfirm = true
                    } label: {
                        Label("清空聊天记录", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .confirmationDialog("清空与 \(contact.name) 的全部聊天记录？",
                            isPresented: $showClearConfirm, titleVisibility: .visible) {
            Button("清空", role: .destructive) {
                Task { await model?.clearAll() }
            }
        }
        .onAppear {
            if model == nil {
                model = ChatViewModel(contact: contact, router: router,
                                      store: store, settings: settings)
            }
        }
    }

    @ViewBuilder
    private func content(_ model: ChatViewModel) -> some View {
        @Bindable var model = model
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 10) {
                        if model.hasMore {
                            Button {
                                Task { await model.loadEarlier() }
                            } label: {
                                if model.loadingEarlier {
                                    ProgressView()
                                } else {
                                    Text("加载更早消息").font(.footnote)
                                }
                            }
                            .padding(.top, 8)
                        }
                        ForEach(model.messages) { message in
                            ChatBubbleView(message: message, contact: contact) {
                                Task { await model.translate(message) }
                            }
                            .id(message.id)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
                // 消息少时从顶部开始排列（不贴底）；新消息到达时滚到底部
                .onChange(of: model.messages.count) {
                    if let last = model.messages.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }
            // 辅助卡片（M3）：中文语音触发，位于输入栏上方
            if model.assistShown {
                AssistCardView(model: model)
            }
            inputBar(model)
        }
        .animation(.easeOut(duration: 0.25), value: model.assistShown)
        // 短提示就地展示（录音太短/语种降级等），2 秒自动消失
        .overlay(alignment: .bottom) {
            if let hint = model.hintText {
                Text(hint)
                    .font(.footnote)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(.black.opacity(0.72), in: Capsule())
                    .padding(.bottom, 72)
                    .transition(.opacity)
                    .task {
                        try? await Task.sleep(for: .seconds(2))
                        withAnimation { model.hintText = nil }
                    }
            }
        }
        .animation(.easeOut(duration: 0.2), value: model.hintText)
        .task { await model.load() }
        .alert("出错了", isPresented: .init(
            get: { model.errorText != nil },
            set: { if !$0 { model.errorText = nil } })
        ) {
            Button("好", role: .cancel) {}
        } message: {
            Text(model.errorText ?? "")
        }
    }

    /// 输入栏：语音/文本双模（对应 Web 端 chat-input-bar）；
    /// 语音模式「按住 说话」→ 录音 → ECAPA 语种分流 → 接口 5b 流式对话
    private func inputBar(_ model: ChatViewModel) -> some View {
        HStack(spacing: 10) {
            // 模式切换：文本态显示麦克风，语音态显示键盘
            Button {
                withAnimation(.easeOut(duration: 0.15)) { voiceMode.toggle() }
            } label: {
                Image(systemName: voiceMode ? "keyboard" : "mic")
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }
            if voiceMode {
                PressTalkButton(
                    label: model.assistShown ? "按住 跟读" : "按住 说话",
                    disabled: model.sending,
                    onStart: { Task { await model.startTalk() } },
                    onSend: { Task { await model.finishTalk() } },
                    onCancel: { model.cancelTalk() })
            } else {
                TextField("输入英文消息…", text: $draft, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.plain)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(.fill.tertiary, in: RoundedRectangle(cornerRadius: 18))
                    .onSubmit { send(model) }
                Button {
                    send(model)
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title)
                }
                .disabled(model.sending
                          || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    private func send(_ model: ChatViewModel) {
        let text = draft
        draft = ""
        Task { await model.sendText(text) }
    }
}

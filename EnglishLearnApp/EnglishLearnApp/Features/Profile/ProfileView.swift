import SwiftUI

/// 我的页（架构文档 §5）：后端服务 / 直连模型 / TTS 设置；API Key 存 Keychain 掩码显示
struct ProfileView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(BackendRouter.self) private var router

    @State private var apiKeyDraft = ""
    @State private var apiKeyMasked = ""
    @State private var editingKey = false
    @State private var testing = false
    @State private var testResult: String?
    /// 统一焦点控制：点「完成」或下拉列表收起键盘
    @FocusState private var fieldFocused: Bool

    var body: some View {
        @Bindable var settings = settings
        NavigationStack {
            Form {
                Section("后端服务") {
                    TextField("后端 Base URL", text: $settings.backendBaseURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($fieldFocused)
                    Button {
                        Task { await testConnection() }
                    } label: {
                        HStack {
                            Text("测试连接")
                            Spacer()
                            if testing {
                                ProgressView()
                            } else if let result = testResult {
                                Text(result).foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                Section {
                    Toggle("后端不可达时直连模型", isOn: $settings.directEnabled)
                    TextField("模型服务地址", text: $settings.dashscopeBaseURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($fieldFocused)
                    TextField("模型名", text: $settings.modelName)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($fieldFocused)
                    apiKeyRow
                } header: {
                    Text("多模态模型（直连模式 · M4）")
                } footer: {
                    Text("直连 qwen3-omni-flash 完成完整对话链路；API Key 仅保存在本机钥匙串。")
                }

                Section("语音合成（云端 TTS）") {
                    TextField("音色", text: $settings.ttsVoice)
                        .textInputAutocapitalization(.never)
                        .focused($fieldFocused)
                    HStack {
                        Text("语速")
                        Slider(value: $settings.speechRate, in: 0.7...1.5, step: 0.1)
                        Text(String(format: "%.1f", settings.speechRate))
                            .font(.callout.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }

                Section("关于") {
                    LabeledContent("当前通道", value: router.channel.label)
                    LabeledContent("版本", value: "0.1.0（M1 骨架）")
                }
            }
            .navigationTitle("我的")
            // 键盘收起：下拉列表交互式收起 + 键盘工具栏「完成」
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("完成") { fieldFocused = false }
                }
            }
            .onAppear { refreshKeyMask() }
        }
    }

    /// API Key：掩码显示，点击后进入编辑；保存写 Keychain（不入 UserDefaults / 不入日志）
    @ViewBuilder
    private var apiKeyRow: some View {
        if editingKey {
            HStack {
                SecureField("sk-…", text: $apiKeyDraft)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($fieldFocused)
                Button("保存") {
                    KeychainStore.save(.dashscopeAPIKey, value: apiKeyDraft)
                    apiKeyDraft = ""
                    editingKey = false
                    refreshKeyMask()
                }
            }
        } else {
            Button {
                editingKey = true
            } label: {
                LabeledContent("API Key", value: apiKeyMasked.isEmpty ? "未配置" : apiKeyMasked)
            }
            .foregroundStyle(.primary)
        }
    }

    private func refreshKeyMask() {
        guard let key = KeychainStore.load(.dashscopeAPIKey), key.count > 8 else {
            apiKeyMasked = ""
            return
        }
        apiKeyMasked = "\(key.prefix(4))••••\(key.suffix(4))"
    }

    /// 设置页手动探测（架构文档 §3.4：force 跳过 30s 缓存）
    private func testConnection() async {
        testing = true
        defer { testing = false }
        let channel = await router.refresh(force: true)
        testResult = channel == .online ? "连接成功" : "无法连接"
    }
}

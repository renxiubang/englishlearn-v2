import Foundation
import Observation
import Security

/// 非敏感配置：UserDefaults（架构文档 §5「我的」页设置项）
@MainActor
@Observable
final class AppSettings {
    /// 自建后端 Base URL（模拟器可用 127.0.0.1 访问宿主机；真机填局域网 IP）
    var backendBaseURL: String {
        didSet { defaults.set(backendBaseURL, forKey: Keys.backendBaseURL) }
    }
    /// 直连模式开关（M4：后端不可达时 App 直连 qwen3-omni-flash）
    var directEnabled: Bool {
        didSet { defaults.set(directEnabled, forKey: Keys.directEnabled) }
    }
    /// dashscope compatible-mode 地址（对齐 backend/.env.example）
    var dashscopeBaseURL: String {
        didSet { defaults.set(dashscopeBaseURL, forKey: Keys.dashscopeBaseURL) }
    }
    /// 多模态模型名
    var modelName: String {
        didSet { defaults.set(modelName, forKey: Keys.modelName) }
    }
    /// 云端 TTS 音色
    var ttsVoice: String {
        didSet { defaults.set(ttsVoice, forKey: Keys.ttsVoice) }
    }
    /// TTS 语速（对齐现有产品 1.1）
    var speechRate: Double {
        didSet { defaults.set(speechRate, forKey: Keys.speechRate) }
    }

    private let defaults: UserDefaults

    private enum Keys {
        static let backendBaseURL = "settings.backendBaseURL"
        static let directEnabled = "settings.directEnabled"
        static let dashscopeBaseURL = "settings.dashscopeBaseURL"
        static let modelName = "settings.modelName"
        static let ttsVoice = "settings.ttsVoice"
        static let speechRate = "settings.speechRate"
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        backendBaseURL = defaults.string(forKey: Keys.backendBaseURL) ?? "http://127.0.0.1:8080"
        directEnabled = defaults.bool(forKey: Keys.directEnabled)
        dashscopeBaseURL = defaults.string(forKey: Keys.dashscopeBaseURL)
            ?? "https://dashscope.aliyuncs.com/compatible-mode/v1"
        modelName = defaults.string(forKey: Keys.modelName) ?? "qwen3-omni-flash"
        ttsVoice = defaults.string(forKey: Keys.ttsVoice) ?? "Cherry"
        speechRate = defaults.object(forKey: Keys.speechRate) as? Double ?? 1.1
    }
}

/// 敏感配置：Keychain（API Key 不入 UserDefaults / 不入日志，架构文档 §2）
enum KeychainStore {
    enum Key: String {
        case dashscopeAPIKey = "dashscope.apiKey"
    }

    static func save(_ key: Key, value: String) {
        let data = Data(value.utf8)
        var query = baseQuery(key)
        SecItemDelete(query as CFDictionary)
        guard !value.isEmpty else { return }
        query[kSecValueData as String] = data
        SecItemAdd(query as CFDictionary, nil)
    }

    static func load(_ key: Key) -> String? {
        var query = baseQuery(key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private static func baseQuery(_ key: Key) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.renxiansheng.englishlearn",
            kSecAttrAccount as String: key.rawValue,
        ]
    }
}

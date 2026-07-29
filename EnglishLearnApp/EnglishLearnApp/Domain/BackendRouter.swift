import Foundation
import Network
import Observation

/// 当前对话通道（架构文档 §3.4）
enum Channel: String {
    case online          // 后端可达 → RemoteBackend
    case direct          // 不可达且已配置模型 Key → DirectBackend（M4）
    case offlineReadOnly // 不可达且未配置 Key → 只读本地历史

    var label: String {
        switch self {
        case .online: return "在线"
        case .direct: return "直连"
        case .offlineReadOnly: return "离线"
        }
    }
}

/// 可达性探测与通道选择（架构文档 §3.4）：
/// GET {backendBaseURL}/healthz 超时 2s + NWPathMonitor；结果缓存 30s。
@MainActor
@Observable
final class BackendRouter {
    private(set) var channel: Channel = .online

    @ObservationIgnored private let settings: AppSettings
    @ObservationIgnored private let remote: RemoteBackend
    @ObservationIgnored private let direct: DirectBackend
    @ObservationIgnored private let pathMonitor = NWPathMonitor()
    @ObservationIgnored private var networkAvailable = true
    @ObservationIgnored private var lastProbeAt: Date?
    @ObservationIgnored private var lastProbeReachable = false
    /// 探测结果缓存 30s，避免每条消息都探测
    @ObservationIgnored private let probeCacheTTL: TimeInterval = 30

    init(settings: AppSettings) {
        self.settings = settings
        self.remote = RemoteBackend(settings: settings)
        self.direct = DirectBackend(settings: settings)
        pathMonitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.networkAvailable = path.status == .satisfied
            }
        }
        pathMonitor.start(queue: DispatchQueue(label: "backend-router.path"))
    }

    /// 当前应使用的后端实现（未探测时按当前 channel 返回）
    var backend: ChatBackend {
        channel == .online ? remote : direct
    }

    /// 探测并刷新通道；force 跳过 30s 缓存（设置页"测试连接"用）
    @discardableResult
    func refresh(force: Bool = false) async -> Channel {
        let reachable = await probeHealthz(force: force)
        let newChannel: Channel
        if reachable {
            newChannel = .online
        } else if settings.directEnabled && KeychainStore.load(.dashscopeAPIKey)?.isEmpty == false {
            newChannel = .direct
        } else {
            newChannel = .offlineReadOnly
        }
        channel = newChannel
        return newChannel
    }

    private func probeHealthz(force: Bool) async -> Bool {
        // 无网络直接判不可达，跳过探测
        guard networkAvailable else { return false }
        if !force, let at = lastProbeAt, Date().timeIntervalSince(at) < probeCacheTTL {
            return lastProbeReachable
        }
        var reachable = false
        if let url = URL(string: settings.backendBaseURL)?.appendingPathComponent("healthz") {
            var request = URLRequest(url: url)
            request.timeoutInterval = 2
            if let (_, response) = try? await URLSession.shared.data(for: request),
               let http = response as? HTTPURLResponse, http.statusCode == 200 {
                reachable = true
            }
        }
        lastProbeAt = Date()
        lastProbeReachable = reachable
        return reachable
    }
}

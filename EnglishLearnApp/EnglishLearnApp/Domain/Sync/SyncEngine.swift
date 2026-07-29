import Foundation

/// 离线消息同步引擎桩（架构文档 §4.4/§4.5，M5 里程碑实现）：
/// 扫描 syncState=pendingUpload 的本地行，经批量导入接口
/// `POST /api/chats/{contactId}/messages/import`（clientId 幂等 + idMap 回写）上行；
/// favorites / progress 靠既有接口幂等重放；服务端 id 为权威。
@MainActor
final class SyncEngine {
    private let store: LocalStore

    init(store: LocalStore) {
        self.store = store
    }

    /// 后端恢复可达时触发（App 进前台 / 通道切回在线）
    func syncPendingIfNeeded() async {
        // M5：批量导入 pendingUpload 消息 → 回写 serverId → syncState=synced
    }
}

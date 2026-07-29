import SwiftData
import SwiftUI

@main
struct EnglishLearnApplication: App {
    @State private var settings: AppSettings
    @State private var store: LocalStore
    @State private var router: BackendRouter

    init() {
        let settings = AppSettings()
        let store = LocalStore()
        _settings = State(initialValue: settings)
        _store = State(initialValue: store)
        _router = State(initialValue: BackendRouter(settings: settings))
        // 首启内置 seed 兜底（含 persona，直连模式对话用）
        store.seedBuiltinContactsIfNeeded()
    }

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environment(settings)
                .environment(store)
                .environment(router)
                .modelContainer(store.container)
                .task {
                    // App 进前台探测可达性（架构文档 §3.4）
                    await router.refresh()
                }
        }
    }
}

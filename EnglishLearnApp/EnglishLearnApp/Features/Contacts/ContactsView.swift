import SwiftUI

/// 联系人列表（对应 Web ContactsView.vue）：本地镜像秒开 + 在线刷新 + 本地关键字过滤
struct ContactsView: View {
    /// 首页入口内嵌时不再套 NavigationStack
    var embedded = false

    @Environment(BackendRouter.self) private var router
    @Environment(LocalStore.self) private var store
    @State private var contacts: [Contact] = []
    @State private var keyword = ""
    @State private var errorText: String?

    var body: some View {
        if embedded {
            content.navigationTitle("对话")
        } else {
            NavigationStack {
                content
                    .navigationTitle("对话")
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) { ChannelBadge() }
                    }
            }
        }
    }

    private var content: some View {
        List(filtered) { contact in
            NavigationLink(value: contact) {
                row(contact)
            }
        }
        .listStyle(.plain)
        .searchable(text: $keyword, prompt: "搜索联系人")
        .navigationDestination(for: Contact.self) { contact in
            ChatView(contact: contact)
        }
        .overlay {
            if filtered.isEmpty {
                ContentUnavailableView(
                    keyword.isEmpty ? "暂无联系人" : "无匹配结果",
                    systemImage: "person.2")
            }
        }
        .task { await load() }
        .refreshable { await load(force: true) }
    }

    private var filtered: [Contact] {
        guard !keyword.isEmpty else { return contacts }
        return contacts.filter {
            $0.name.localizedCaseInsensitiveContains(keyword)
                || $0.sub.localizedCaseInsensitiveContains(keyword)
        }
    }

    private func row(_ contact: Contact) -> some View {
        HStack(spacing: 12) {
            ContactAvatarView(contact: contact)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(contact.name).font(.body.weight(.medium))
                    if let tag = contact.tag, !tag.isEmpty {
                        Text(tag)
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.blue.opacity(0.1), in: Capsule())
                            .foregroundStyle(.blue)
                    }
                }
                if !contact.sub.isEmpty {
                    Text(contact.sub).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }

    /// 本地优先读（架构文档 §4.3）：先镜像渲染，在线拉取后覆盖
    private func load(force: Bool = false) async {
        if contacts.isEmpty {
            contacts = store.loadContacts()
        }
        await router.refresh(force: force)
        guard router.channel == .online else { return }
        do {
            let fresh = try await router.backend.fetchContacts()
            contacts = fresh
            store.upsertContacts(fresh)
        } catch {
            errorText = error.localizedDescription
        }
    }
}

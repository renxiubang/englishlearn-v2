import SwiftUI

/// Tab 骨架：镜像 Web 端 TabBar（首页 / 对话 / 分享 / 我的）
struct RootTabView: View {
    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("首页", systemImage: "house") }
            ContactsView()
                .tabItem { Label("对话", systemImage: "bubble.left.and.bubble.right") }
            PlaceholderView(title: "分享", note: "英语秀场 · 敬请期待")
                .tabItem { Label("分享", systemImage: "paperplane") }
            ProfileView()
                .tabItem { Label("我的", systemImage: "person") }
        }
    }
}

/// 未移植模块占位页（对应 Web 端 PlaceholderView.vue）
struct PlaceholderView: View {
    let title: String
    let note: String

    var body: some View {
        NavigationStack {
            ContentUnavailableView(note, systemImage: "hammer")
                .navigationTitle(title)
        }
    }
}

/// 联系人头像：AI 用 emoji + 底色；真人 dicebear 为 SVG（AsyncImage 不支持），
/// 降级为名称首字符圆形头像
struct ContactAvatarView: View {
    let contact: Contact
    var size: CGFloat = 48

    var body: some View {
        ZStack {
            Circle().fill(background)
            if contact.type == "ai", let emoji = contact.emoji {
                Text(emoji).font(.system(size: size * 0.5))
            } else {
                Text(String(contact.name.prefix(1)))
                    .font(.system(size: size * 0.42, weight: .semibold))
                    .foregroundStyle(.white)
            }
        }
        .frame(width: size, height: size)
    }

    private var background: Color {
        if contact.type == "ai", let hex = contact.avatarBg, let color = Color(hex: hex) {
            return color
        }
        // 真人头像底色按 id 稳定取色
        let palette: [Color] = [.blue, .teal, .indigo, .orange, .pink, .mint]
        let index = abs(contact.id.hashValue) % palette.count
        return palette[index].opacity(0.85)
    }
}

extension Color {
    /// "#rrggbb" 解析（接口 3 的 avatarBg）
    init?(hex: String) {
        var value = hex.trimmingCharacters(in: .whitespaces)
        guard value.hasPrefix("#") else { return nil }
        value.removeFirst()
        guard value.count == 6, let rgb = UInt64(value, radix: 16) else { return nil }
        self.init(
            red: Double((rgb >> 16) & 0xFF) / 255,
            green: Double((rgb >> 8) & 0xFF) / 255,
            blue: Double(rgb & 0xFF) / 255)
    }
}

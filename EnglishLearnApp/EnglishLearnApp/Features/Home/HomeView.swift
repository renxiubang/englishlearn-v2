import SwiftUI

/// 首页：问候 + 学习统计 + 练习入口（接口 1/2 依赖后端 user 模块，M6 补齐，先展示默认值）
struct HomeView: View {
    @Environment(BackendRouter.self) private var router

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    greetingCard
                    statsRow
                    entriesSection
                }
                .padding()
            }
            .navigationTitle("首页")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    ChannelBadge()
                }
            }
        }
    }

    private var greetingCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Hi, Amy 👋")
                .font(.title2.bold())
            Text("今天也来练一段口语吧")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
    }

    private var statsRow: some View {
        HStack(spacing: 12) {
            statCard(value: "—", label: "今日分钟")
            statCard(value: "—", label: "连续打卡")
            statCard(value: "Lv.6", label: "口语达人")
        }
    }

    private func statCard(value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Text(value).font(.headline)
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(.fill.tertiary, in: RoundedRectangle(cornerRadius: 12))
    }

    private var entriesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("练习")
                .font(.headline)
            NavigationLink {
                ContactsView(embedded: true)
            } label: {
                entryRow(icon: "bubble.left.and.bubble.right.fill", tint: .blue,
                         title: "对话陪练", sub: "和 AI / 家人聊聊今天")
            }
            NavigationLink {
                PictureStoryView()
            } label: {
                entryRow(icon: "photo.on.rectangle.angled", tint: .orange,
                         title: "看图讲故事", sub: "看图开口，讲一个小故事")
            }
        }
    }

    private func entryRow(icon: String, tint: Color, title: String, sub: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(tint)
                .frame(width: 44, height: 44)
                .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body.weight(.medium)).foregroundStyle(.primary)
                Text(sub).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(12)
        .background(.fill.tertiary, in: RoundedRectangle(cornerRadius: 14))
    }
}

/// 通道状态角标（架构文档 §3.4：在线 / 直连 / 离线）
struct ChannelBadge: View {
    @Environment(BackendRouter.self) private var router

    var body: some View {
        let channel = router.channel
        Text(channel.label)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }

    private var color: Color {
        switch router.channel {
        case .online: return .green
        case .direct: return .blue
        case .offlineReadOnly: return .gray
        }
    }
}

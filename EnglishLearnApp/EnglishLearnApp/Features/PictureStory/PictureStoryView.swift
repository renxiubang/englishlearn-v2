import SwiftUI

/// 看图讲故事（M6 里程碑：接口 7/8/12-15，依赖后端 pic-story 模块补齐）
struct PictureStoryView: View {
    var body: some View {
        ContentUnavailableView(
            "看图讲故事将在 M6 里程碑提供",
            systemImage: "photo.on.rectangle.angled",
            description: Text("看图开口讲故事、逐句评分与 ⭐ 进度")
        )
        .navigationTitle("看图讲故事")
        .navigationBarTitleDisplayMode(.inline)
    }
}

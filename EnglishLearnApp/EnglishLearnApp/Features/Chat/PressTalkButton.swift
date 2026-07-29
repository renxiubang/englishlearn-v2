import SwiftUI

/// 按住说话按钮（对应 web/src/components/PressTalkButton.vue）：
/// 按下进入录音态并回调 onStart，上滑超过 60pt 进入取消态，
/// 松手时按是否取消分别回调 onCancel / onSend。
struct PressTalkButton: View {
    var label: String = "按住 说话"
    var pressingLabel: String = "松开 发送"
    var cancelLabel: String = "松开 取消"
    var disabled: Bool = false
    var onStart: () -> Void = {}
    var onSend: () -> Void
    var onCancel: () -> Void = {}

    @State private var pressing = false
    @State private var cancelling = false

    /// 上滑取消阈值（对齐 Web 端 60px）
    private let cancelDistance: CGFloat = 60

    var body: some View {
        Text(currentLabel)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(pressing ? .white : .primary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(
                pressing ? AnyShapeStyle(Color.accentColor) : AnyShapeStyle(.fill.tertiary),
                in: Capsule()
            )
            .scaleEffect(pressing ? 0.98 : 1)
            .opacity(disabled ? 0.35 : 1)
            .animation(.easeOut(duration: 0.12), value: pressing)
            .gesture(pressGesture)
    }

    private var currentLabel: String {
        guard pressing else { return label }
        return cancelling ? cancelLabel : pressingLabel
    }

    private var pressGesture: some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { value in
                guard !disabled else { return }
                if !pressing {
                    pressing = true
                    cancelling = false
                    onStart()
                }
                cancelling = -value.translation.height > cancelDistance
            }
            .onEnded { _ in
                guard pressing else { return }
                let cancelled = cancelling
                pressing = false
                cancelling = false
                cancelled ? onCancel() : onSend()
            }
    }
}

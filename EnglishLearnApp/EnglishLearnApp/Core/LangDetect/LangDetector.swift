import Foundation
import OnnxRuntimeBindings

/// ECAPA-TDNN 语种判断（对应 web useLangDetect.ts）：输入 16kHz Float32，输出中/英，
/// 决定「按住说话」走接口 5b（英文对话）还是接口 16（中文翻译辅助）。
/// 模型 Resources/ecapa_lang_id_int8.onnx（107 类，zh=106 / en=20），
/// 输入名 waveform [1, N]、输出名 logits；加载/推理失败降级英文（warnedFallback 供 UI 提示一次）。
final class LangDetector {
    static let shared = LangDetector()

    private static let zhIndex = 106
    private static let enIndex = 20
    /// 2s @ 16kHz
    private static let maxSamples = 32000

    private var session: ORTSession?
    private var env: ORTEnv?
    private var loadFailed = false
    /// 降级提示是否已给过一次（对齐 web 端 warned）
    private(set) var warnedFallback = false

    /// 提前加载模型（首次按住说话时调用），失败静默降级
    func preload() {
        _ = ensureSession()
    }

    /// 判断语种；模型不可用或推理异常时降级返回 "en"
    func detect(samples: [Float]) -> String {
        guard let session = ensureSession() else {
            warnedFallback = true
            return "en"
        }
        do {
            let input = Array(samples.prefix(Self.maxSamples))
            let data = input.withUnsafeBufferPointer { Data(buffer: $0) }
            let tensor = try ORTValue(
                tensorData: NSMutableData(data: data),
                elementType: .float,
                shape: [1, NSNumber(value: input.count)])
            let outputs = try session.run(
                withInputs: ["waveform": tensor],
                outputNames: ["logits"],
                runOptions: nil)
            guard let logits = outputs["logits"] else { return "en" }
            let raw = try logits.tensorData() as Data
            let values: [Float] = raw.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
            guard values.count > Self.zhIndex else { return "en" }
            return values[Self.enIndex] > values[Self.zhIndex] ? "en" : "zh"
        } catch {
            return "en"
        }
    }

    private func ensureSession() -> ORTSession? {
        if let session { return session }
        guard !loadFailed else { return nil }
        guard let path = Bundle.main.path(forResource: "ecapa_lang_id_int8", ofType: "onnx") else {
            loadFailed = true
            return nil
        }
        do {
            let env = try ORTEnv(loggingLevel: .warning)
            let session = try ORTSession(env: env, modelPath: path, sessionOptions: nil)
            self.env = env
            self.session = session
            return session
        } catch {
            loadFailed = true
            return nil
        }
    }
}

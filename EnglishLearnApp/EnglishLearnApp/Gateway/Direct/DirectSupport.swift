import Foundation

/// 直连通道共享工具（M4）：与后端 gateway/sentence.py、tts.py、speech/service.py 同源移植。
/// 断句、emoji 过滤、时长格式化、本地音频落盘，供 DirectMLLMClient/CloudTTSClient/DirectOrchestrator 复用。

// MARK: - 时长格式化（对齐 speech/service.py fmt_duration）

/// 秒 → "m:ss" 展示格式（api.md duration 字段）
func fmtDuration(_ seconds: Double) -> String {
    let total = max(0, Int(seconds.rounded()))
    return "\(total / 60):" + String(format: "%02d", total % 60)
}

// MARK: - 断句（对齐 sentence.py / orchestrator.py 的 _SENTENCE_END = (?<=[.!?])\s+）

/// 句末标点后接空白处切分（等价 Python re.split(r"(?<=[.!?])\s+", s)，保留末段）
private func splitOnSentenceEnd(_ s: String) -> [String] {
    var parts: [String] = []
    var current = ""
    let chars = Array(s)
    var i = 0
    while i < chars.count {
        let c = chars[i]
        if c.isWhitespace, let last = current.last, ".!?".contains(last) {
            parts.append(current)
            current = ""
            while i < chars.count, chars[i].isWhitespace { i += 1 }
            continue
        }
        current.append(c)
        i += 1
    }
    parts.append(current)
    return parts
}

/// orchestrator.py _split_sentences：切分并去空白、丢弃空段
func splitSentences(_ text: String) -> [String] {
    splitOnSentenceEnd(text)
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
}

/// 流式断句累积器（对齐 sentence.py SentenceAccumulator）：
/// 累积流式 token 吐出完整句；过短句（< minLen）与后续合并，避免碎片化 TTS 调用。
final class SentenceAccumulator {
    private var buf = ""
    private let minLen: Int

    init(minLen: Int = 8) { self.minLen = minLen }

    /// 喂入增量，返回本次可发射的完整句子列表
    func push(_ delta: String) -> [String] {
        buf += delta
        var parts = splitOnSentenceEnd(buf)
        let remainder = parts.removeLast()  // 末段未见句末+空白，视为未完成
        var out: [String] = []
        var acc = ""
        for p in parts {
            acc = acc.isEmpty
                ? p.trimmingCharacters(in: .whitespaces)
                : "\(acc) \(p)".trimmingCharacters(in: .whitespaces)
            if acc.count >= minLen {
                out.append(acc)
                acc = ""
            }
        }
        // 不足最小长度的短句回填缓冲，与后续增量继续合并
        buf = acc.isEmpty ? remainder : "\(acc) \(remainder)"
        return out
    }

    /// 流结束取缓冲区剩余（若有）
    func flush() -> String? {
        let tail = buf.trimmingCharacters(in: .whitespacesAndNewlines)
        buf = ""
        return tail.isEmpty ? nil : tail
    }
}

// MARK: - emoji 过滤（对齐 tts.py strip_emoji）

private let emojiRegex = try? NSRegularExpression(
    pattern: "[\\x{1F1E6}-\\x{1FAFF}\\x{2600}-\\x{27BF}\\x{2B00}-\\x{2BFF}\\x{FE0E}\\x{FE0F}\\x{200D}\\x{20E3}]+")

/// 去除 emoji 后归并多余空白，避免 TTS 读出表情符号
func stripEmoji(_ text: String) -> String {
    var cleaned = text
    if let re = emojiRegex {
        let range = NSRange(text.startIndex..., in: text)
        cleaned = re.stringByReplacingMatches(in: text, range: range, withTemplate: "")
    }
    return cleaned
        .replacingOccurrences(of: "\\s{2,}", with: " ", options: .regularExpression)
        .trimmingCharacters(in: .whitespaces)
}

// MARK: - 本地音频落盘（对齐架构文档 §4.2：Documents/audio/）

/// 直连模式音频落盘：与 FilePlayer 缓存目录同为 Documents/audio/，
/// 故存文件名即可被 FilePlayer 命中缓存离线回放（无需远端 URL）。
enum DirectAudioStore {
    static var audioDir: URL {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("audio", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// 写入 wav 并返回存库用的相对文件名（FilePlayer 按 lastPathComponent 命中缓存）
    @discardableResult
    static func writeWav(_ data: Data, name: String) -> String {
        try? data.write(to: audioDir.appendingPathComponent(name))
        return name
    }
}

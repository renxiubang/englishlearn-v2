import Foundation

/// POST-SSE 逐行解析（架构文档 §3.2，对应 web/src/api/sse.ts 的 fetch + ReadableStream 方案）：
/// `URLSession.bytes(for:)` 读到的行按空行分帧，解析 `event:` / `data:` 字段。
struct SSEFrame {
    let event: String
    let data: String
}

/// 增量行解析器：喂入单行文本，凑齐一帧（遇空行）时返回
struct SSELineParser {
    private var event = ""
    private var dataLines: [String] = []

    mutating func feed(line: String) -> SSEFrame? {
        if line.isEmpty {
            defer { event = ""; dataLines = [] }
            guard !event.isEmpty || !dataLines.isEmpty else { return nil }
            return SSEFrame(event: event, data: dataLines.joined(separator: "\n"))
        }
        if line.hasPrefix("event:") {
            event = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces)
        } else if line.hasPrefix("data:") {
            dataLines.append(String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces))
        }
        // 其余字段（id:/retry:/注释行）当前契约未使用，忽略
        return nil
    }
}

extension SSEFrame {
    /// data 载荷 JSON 解码
    func payload<T: Decodable>(_ type: T.Type) -> T? {
        try? JSONDecoder().decode(type, from: Data(data.utf8))
    }
}

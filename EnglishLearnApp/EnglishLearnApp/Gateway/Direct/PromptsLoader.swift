import Foundation

/// 提示词加载器（M4，对齐 backend/app/gateway/prompts.py get_prompt）。
/// Resources/Prompts.yaml 与后端 prompts.yaml 同源维护；直连模式无后端可达，
/// 由 App 内置副本提供任务提示词（persona 仍来自本地 seed）。
/// Swift 无内置 YAML：本文件的极简解析器仅支持本项目使用的「key: |」块标量格式。
enum PromptsLoader {
    /// 首次访问时懒加载并缓存（7 个任务键）
    static let all: [String: String] = load()

    static func get(_ key: String) -> String { all[key] ?? "" }

    private static func load() -> [String: String] {
        guard let url = Bundle.main.url(forResource: "Prompts", withExtension: "yaml"),
              let content = try? String(contentsOf: url, encoding: .utf8) else {
            return [:]
        }
        return parse(content)
    }

    /// 解析「key: |」块标量：顶格键 + 2 空格缩进多行内容，忽略注释/空行分隔。
    static func parse(_ content: String) -> [String: String] {
        var result: [String: String] = [:]
        let lines = content.components(separatedBy: "\n")
        var i = 0
        while i < lines.count {
            guard let key = blockKey(lines[i]) else { i += 1; continue }
            i += 1
            var block: [String] = []
            while i < lines.count {
                let line = lines[i]
                if line.trimmingCharacters(in: .whitespaces).isEmpty {
                    block.append("")
                    i += 1
                } else if line.hasPrefix("  ") {
                    block.append(String(line.dropFirst(2)))  // 去 2 空格缩进
                    i += 1
                } else {
                    break  // 顶格非空行 → 块结束
                }
            }
            result[key] = block.joined(separator: "\n")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return result
    }

    /// 顶格「key: |」行 → 键名（否则 nil）
    private static func blockKey(_ line: String) -> String? {
        guard !line.hasPrefix(" "), !line.hasPrefix("#"),
              let colon = line.firstIndex(of: ":") else { return nil }
        let key = String(line[..<colon])
        let rest = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
        guard rest == "|",
              !key.isEmpty,
              key.allSatisfy({ $0.isLetter || $0.isNumber || $0 == "_" }) else { return nil }
        return key
    }
}

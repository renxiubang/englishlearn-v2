import Foundation

/// URLSession 封装：统一包裹 `{code, data, message}` 解析与错误码语义，
/// 与 Web 端 `http.ts` 一致（架构文档 §3.2）。
struct HTTPClient {
    var timeout: TimeInterval = 15

    func get<T: Decodable>(_ url: URL) async throws -> T {
        try await request(url, method: "GET", body: nil)
    }

    func post<T: Decodable>(_ url: URL, json: [String: Any]? = nil) async throws -> T {
        var body: Data?
        if let json {
            body = try? JSONSerialization.data(withJSONObject: json)
        }
        return try await request(url, method: "POST", body: body)
    }

    func delete<T: Decodable>(_ url: URL) async throws -> T {
        try await request(url, method: "DELETE", body: nil)
    }

    private func request<T: Decodable>(_ url: URL, method: String, body: Data?) async throws -> T {
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = timeout
        if let body {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        // 预留 JWT：当前单用户免登阶段无需携带（api.md 通用约定）

        let data: Data
        do {
            (data, _) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError.network(error)
        }
        return try Self.decodeEnvelope(data)
    }

    /// 统一包裹解码：code != 0 抛业务错误（HTTP 状态码与 code 同步，以 body 为准）
    static func decodeEnvelope<T: Decodable>(_ data: Data) throws -> T {
        guard let envelope = try? JSONDecoder().decode(ApiResponse<T>.self, from: data) else {
            throw APIError.invalidResponse
        }
        guard envelope.code == 0 else {
            throw APIError.business(code: envelope.code, message: envelope.message)
        }
        guard let payload = envelope.data else {
            throw APIError.invalidResponse
        }
        return payload
    }
}

/// multipart/form-data 构造（接口 5b/7/16/17，M2 起使用）
struct MultipartBody {
    let boundary = "Boundary-\(UUID().uuidString)"
    private var body = Data()

    var contentType: String { "multipart/form-data; boundary=\(boundary)" }

    mutating func addField(name: String, value: String) {
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".utf8))
        body.append(Data("\(value)\r\n".utf8))
    }

    mutating func addFile(name: String, filename: String, mimeType: String, data: Data) {
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data(
            "Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n".utf8))
        body.append(Data("Content-Type: \(mimeType)\r\n\r\n".utf8))
        body.append(data)
        body.append(Data("\r\n".utf8))
    }

    func finalized() -> Data {
        var data = body
        data.append(Data("--\(boundary)--\r\n".utf8))
        return data
    }
}

import AVFoundation
import Foundation
import os

private let audioLog = Logger(subsystem: "EnglishLearnApp", category: "Audio")

// MARK: - 音频会话

/// AVAudioSession 切换（架构文档 §7.1）：录音 playAndRecord + 扬声器，播放 playback
enum AudioSessionHelper {
    static func activateRecord() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
        try session.setActive(true)
    }

    static func activatePlayback() {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playback, mode: .default)
            try session.setActive(true)
        } catch {
            audioLog.error("activatePlayback failed: \(error.localizedDescription)")
        }
    }
}

// MARK: - WAV 编码

enum WavCodec {
    /// Float32 样本 → 16-bit PCM WAV（对齐 web useRecorder.ts encodeWav）
    static func encodeWav(samples: [Float], sampleRate: Int) -> Data {
        var pcm = Data(capacity: samples.count * 2)
        for sample in samples {
            let clamped = max(-1, min(1, sample))
            let value = Int16(clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF)
            withUnsafeBytes(of: value.littleEndian) { pcm.append(contentsOf: $0) }
        }
        return encodeWav(pcm: pcm, sampleRate: sampleRate)
    }

    /// Int16 PCM mono 裸流 → WAV（44 字节头）
    static func encodeWav(pcm: Data, sampleRate: Int) -> Data {
        var data = Data()
        func append(_ text: String) { data.append(Data(text.utf8)) }
        func append32(_ value: UInt32) {
            withUnsafeBytes(of: value.littleEndian) { data.append(contentsOf: $0) }
        }
        func append16(_ value: UInt16) {
            withUnsafeBytes(of: value.littleEndian) { data.append(contentsOf: $0) }
        }
        append("RIFF"); append32(UInt32(36 + pcm.count)); append("WAVE")
        append("fmt "); append32(16); append16(1); append16(1)
        append32(UInt32(sampleRate)); append32(UInt32(sampleRate * 2))
        append16(2); append16(16)
        append("data"); append32(UInt32(pcm.count))
        data.append(pcm)
        return data
    }
}

// MARK: - 录音

/// 录音（对应 web useRecorder.ts）：AVAudioEngine tap 采集硬件采样率 Float32
/// → 最近邻抽取重采样 16kHz mono → Int16 WAV；≤60s 上限，<0.5s 由调用方判定
final class Recorder {
    static let targetRate = 16000
    static let maxSeconds = 60

    struct Recording {
        /// 16kHz mono 16-bit WAV
        let wav: Data
        /// 16kHz Float32 采样（供 ECAPA 语种判断）
        let samples: [Float]
        let seconds: Double
    }

    private let engine = AVAudioEngine()
    private let lock = NSLock()
    private var chunks: [[Float]] = []
    private var capturing = false
    private var srcRate = Double(targetRate)
    /// 达到 60 秒上限时回调一次（主线程）
    var onLimit: (() -> Void)?

    /// 请求麦克风权限并开始采集；不可用返回 false
    func start() async -> Bool {
        guard !capturing else { return true }
        guard await AVAudioApplication.requestRecordPermission() else { return false }
        do { try AudioSessionHelper.activateRecord() } catch { return false }

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        srcRate = format.sampleRate
        lock.lock(); chunks = []; lock.unlock()

        let maxFrames = Int(format.sampleRate) * Self.maxSeconds
        var total = 0
        var limitHit = false
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            guard let self, self.capturing,
                  let channel = buffer.floatChannelData?[0] else { return }
            let count = Int(buffer.frameLength)
            self.lock.lock()
            if total < maxFrames {
                self.chunks.append(Array(UnsafeBufferPointer(start: channel, count: count)))
                total += count
                if total >= maxFrames, !limitHit {
                    limitHit = true
                    DispatchQueue.main.async { self.onLimit?() }
                }
            }
            self.lock.unlock()
        }
        engine.prepare()
        do { try engine.start() } catch {
            input.removeTap(onBus: 0)
            return false
        }
        capturing = true
        return true
    }

    /// 停止并产出录音；未在采集或无有效数据返回 nil
    func stop() -> Recording? {
        guard capturing else { return nil }
        capturing = false
        teardown()
        lock.lock()
        let merged = chunks.flatMap { $0 }
        chunks = []
        lock.unlock()
        guard !merged.isEmpty else { return nil }
        let samples = Self.resample(merged, from: srcRate)
        return Recording(
            wav: WavCodec.encodeWav(samples: samples, sampleRate: Self.targetRate),
            samples: samples,
            seconds: Double(samples.count) / Double(Self.targetRate))
    }

    /// 取消（上滑取消）：丢弃已采集数据
    func cancel() {
        guard capturing else { return }
        capturing = false
        teardown()
        lock.lock(); chunks = []; lock.unlock()
    }

    private func teardown() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
    }

    /// 最近邻抽取重采样（对齐 web resampleTo16k）
    private static func resample(_ samples: [Float], from srcRate: Double) -> [Float] {
        let target = Double(targetRate)
        guard srcRate != target else { return samples }
        let ratio = srcRate / target
        let newLen = Int(Double(samples.count) / ratio)
        var out = [Float](repeating: 0, count: newLen)
        for i in 0..<newLen { out[i] = samples[Int(Double(i) * ratio)] }
        return out
    }
}

// MARK: - PCM 分片流式播放

/// SSE 分片流式播放器（对应 web usePcmPlayer.createPcmPlayer）：
/// Int16 PCM mono 24kHz 裸流 → Float32 buffer，AVAudioPlayerNode 按序 schedule 边收边播。
/// 录音会切换音频会话配置使旧音频图失效，故 stop 时拆除、下次 feed 在当前会话下重建
final class PcmStreamPlayer {
    private let engine = AVAudioEngine()
    private let node = AVAudioPlayerNode()
    private let format = AVAudioFormat(standardFormatWithSampleRate: 24000, channels: 1)!
    private var attached = false

    /// 喂入一个解码后的 PCM 分片，立即排期播放
    func feed(_ pcm: Data) {
        let count = pcm.count / 2
        guard count > 0,
              let buffer = AVAudioPCMBuffer(pcmFormat: format,
                                            frameCapacity: AVAudioFrameCount(count)) else { return }
        buffer.frameLength = AVAudioFrameCount(count)
        let dst = buffer.floatChannelData![0]
        pcm.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            let int16 = raw.bindMemory(to: Int16.self)
            for i in 0..<count { dst[i] = Float(Int16(littleEndian: int16[i])) / 32768 }
        }
        ensureRunning()
        guard engine.isRunning else { return }   // 引擎启动失败时跳过，避免 node.play 抛 NSException
        node.scheduleBuffer(buffer)
        if !node.isPlaying { node.play() }
    }

    /// 停止并拆除音频图（丢弃已排期分片），下次 feed 重建
    func stop() {
        guard attached else { return }
        node.stop()
        engine.stop()
        engine.detach(node)
        attached = false
    }

    private func ensureRunning() {
        AudioSessionHelper.activatePlayback()
        if !attached {
            engine.attach(node)
            engine.connect(node, to: engine.mainMixerNode, format: format)
            attached = true
        }
        if !engine.isRunning {
            engine.prepare()
            do { try engine.start() } catch {
                audioLog.error("PcmStreamPlayer engine start failed: \(error.localizedDescription)")
            }
        }
    }
}

// MARK: - 整段回放

/// 整段音频回放（对应 web playUrl/stopUrl）：全局单例，新播放打断上一个；
/// 远端 /audio/*.wav 先缓存到 Documents/audio/ 再播（架构文档 §4.2）
@MainActor
final class FilePlayer: NSObject, AVAudioPlayerDelegate {
    static let shared = FilePlayer()

    private var player: AVAudioPlayer?
    private var onEnded: (() -> Void)?
    private var loadTask: Task<Void, Never>?

    /// 播放音频引用；url 为 `/audio/…` 相对路径时拼 baseURL 下载缓存后播放。
    /// rate 用于慢速（如 0.7）
    func play(url: String, baseURL: String, rate: Float = 1, onEnded: (() -> Void)? = nil) {
        stop()
        self.onEnded = onEnded
        loadTask = Task { [weak self] in
            let data = await Self.load(url: url, baseURL: baseURL)
            guard let self, !Task.isCancelled else { return }
            guard let data else {
                self.finish()
                return
            }
            self.startPlayback(data: data, rate: rate)
        }
    }

    /// 播放本地音频数据（跟读录音回放等，对应 web playBlob）
    func play(data: Data, rate: Float = 1, onEnded: (() -> Void)? = nil) {
        stop()
        self.onEnded = onEnded
        startPlayback(data: data, rate: rate)
    }

    /// 停止当前播放（触发未完成播放的 onEnded，便于 UI 复位）
    func stop() {
        loadTask?.cancel()
        loadTask = nil
        player?.stop()
        player = nil
        finish()
    }

    private func startPlayback(data: Data, rate: Float) {
        AudioSessionHelper.activatePlayback()
        guard let player = try? AVAudioPlayer(data: data) else {
            finish()
            return
        }
        player.delegate = self
        if rate != 1 {
            player.enableRate = true
            player.rate = rate
        }
        player.play()
        self.player = player
    }

    private func finish() {
        let callback = onEnded
        onEnded = nil
        callback?()
    }

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor [weak self] in
            self?.player = nil
            self?.finish()
        }
    }

    /// 缓存优先加载：Documents/audio/{文件名} 命中直接读，否则远端下载并写缓存
    private nonisolated static func load(url: String, baseURL: String) async -> Data? {
        let name = URL(string: url)?.lastPathComponent ?? (url as NSString).lastPathComponent
        let cacheDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("audio", isDirectory: true)
        let cacheFile = cacheDir.appendingPathComponent(name)
        if let cached = try? Data(contentsOf: cacheFile) { return cached }

        let absolute = url.hasPrefix("http") ? url : baseURL + url
        guard let remote = URL(string: absolute),
              let (data, response) = try? await URLSession.shared.data(from: remote),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        try? FileManager.default.createDirectory(at: cacheDir, withIntermediateDirectories: true)
        try? data.write(to: cacheFile)
        return data
    }
}

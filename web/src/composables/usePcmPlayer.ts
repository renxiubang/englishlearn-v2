// 音频播放：
// 1) createPcmPlayer —— SSE 分片流式播放器（后端分片为 Int16 PCM mono 24kHz 裸流 base64），
//    AudioContext 按 nextTime 顺序排期，实现"边收边播"（参考 ai-v2 流式播放）。
// 2) playUrl / playBlob / stopUrl —— HTMLAudio 整段播放（重播 /audio/*.wav、慢速、跟读回放）。

const PCM_SAMPLE_RATE = 24000

export interface PcmPlayer {
  /** 喂入一个 base64 分片，立即排期播放 */
  feed: (base64: string) => void
  /** 停止所有已排期分片 */
  stop: () => void
  /** 停止并释放 AudioContext */
  dispose: () => void
}

export function createPcmPlayer(): PcmPlayer {
  let ctx: AudioContext | null = null
  let nextTime = 0
  let sources: AudioBufferSourceNode[] = []

  function feed(base64: string) {
    if (!ctx) {
      ctx = new AudioContext({ sampleRate: PCM_SAMPLE_RATE })
      nextTime = 0
    }
    const bin = atob(base64)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    const int16 = new Int16Array(bytes.buffer, 0, bytes.length >> 1)
    if (!int16.length) return
    const f32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) f32[i] = int16[i] / 32768
    const buf = ctx.createBuffer(1, f32.length, PCM_SAMPLE_RATE)
    buf.getChannelData(0).set(f32)
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    const t = Math.max(ctx.currentTime, nextTime)
    src.start(t)
    nextTime = t + buf.duration
    sources.push(src)
    src.onended = () => {
      sources = sources.filter((s) => s !== src)
    }
  }

  function stop() {
    for (const s of sources) {
      try {
        s.stop()
      } catch {
        /* 已结束 */
      }
    }
    sources = []
    nextTime = 0
  }

  function dispose() {
    stop()
    ctx?.close().catch(() => {})
    ctx = null
  }

  return { feed, stop, dispose }
}

// ---------- 整段音频播放（全局单例：新的播放打断上一个） ----------
let audioEl: HTMLAudioElement | null = null
let endedCb: (() => void) | null = null
let objectUrl: string | null = null

/** 停止当前整段播放（会触发未完成播放的 onEnded，便于 UI 复位） */
export function stopUrl() {
  if (!audioEl) return
  audioEl.pause()
  audioEl.onended = null
  audioEl = null
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = null
  }
  const cb = endedCb
  endedCb = null
  cb?.()
}

/** 播放 URL（后端 /audio/*.wav）；rate 用于慢速（如 0.7） */
export function playUrl(url: string, rate = 1, onEnded?: () => void) {
  stopUrl()
  audioEl = new Audio(url)
  audioEl.playbackRate = rate
  endedCb = onEnded ?? null
  audioEl.onended = () => {
    const cb = endedCb
    endedCb = null
    audioEl = null
    cb?.()
  }
  audioEl.play().catch(() => {
    stopUrl()
  })
}

/** 播放本地 Blob（跟读录音回放），结束自动释放 object URL */
export function playBlob(blob: Blob, onEnded?: () => void) {
  const url = URL.createObjectURL(blob)
  playUrl(url, 1, onEnded)
  objectUrl = url
}

// 录音 composable：getUserMedia → AudioContext(ScriptProcessor) 采集 Float32
// → 线性重采样 16kHz mono → 16-bit WAV（符合后端上传白名单：wav、≤60s）
// 参考 ai-v2 recordPcm / resampleTo16k / float32ToWavBase64 的实现方式
import { toast } from '@/composables/useToast'

const TARGET_RATE = 16000
const MAX_SECONDS = 60

export interface Recording {
  /** 16kHz mono 16-bit wav */
  blob: Blob
  /** 16kHz Float32 采样（供 ECAPA 语种判断） */
  samples: Float32Array
  seconds: number
}

function resampleTo16k(samples: Float32Array, srcRate: number): Float32Array {
  if (srcRate === TARGET_RATE) return samples
  const ratio = srcRate / TARGET_RATE
  const newLen = Math.floor(samples.length / ratio)
  const out = new Float32Array(newLen)
  for (let i = 0; i < newLen; i++) out[i] = samples[Math.floor(i * ratio)]
  return out
}

function encodeWav(samples: Float32Array): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2)
  const v = new DataView(buf)
  const w = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i))
  }
  w(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); w(8, 'WAVE'); w(12, 'fmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, TARGET_RATE, true); v.setUint32(28, TARGET_RATE * 2, true); v.setUint16(32, 2, true)
  v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

export function useRecorder() {
  let ctx: AudioContext | null = null
  let stream: MediaStream | null = null
  let source: MediaStreamAudioSourceNode | null = null
  let processor: ScriptProcessorNode | null = null
  let chunks: Float32Array[] = []
  let capturing = false

  function teardown() {
    processor?.disconnect()
    source?.disconnect()
    stream?.getTracks().forEach((t) => t.stop())
    ctx?.close().catch(() => {})
    processor = null
    source = null
    stream = null
    ctx = null
  }

  /** 开始采集；麦克风不可用返回 false */
  async function start(): Promise<boolean> {
    if (capturing) return true
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch {
      toast('无法访问麦克风，请检查权限')
      return false
    }
    ctx = new AudioContext()
    source = ctx.createMediaStreamSource(stream)
    processor = ctx.createScriptProcessor(4096, 1, 1)
    chunks = []
    capturing = true
    const maxLen = ctx.sampleRate * MAX_SECONDS
    let total = 0
    let limitHit = false
    processor.onaudioprocess = (e) => {
      if (!capturing || total >= maxLen) return
      const data = e.inputBuffer.getChannelData(0)
      chunks.push(new Float32Array(data))
      total += data.length
      if (total >= maxLen && !limitHit) {
        limitHit = true
        toast('录音已达 60 秒上限')
      }
    }
    source.connect(processor)
    processor.connect(ctx.destination)
    return true
  }

  /** 停止并产出录音；未在采集或无有效数据返回 null */
  function stop(): Recording | null {
    if (!capturing) return null
    capturing = false
    const srcRate = ctx?.sampleRate ?? TARGET_RATE
    teardown()
    const totalLen = chunks.reduce((s, c) => s + c.length, 0)
    const merged = new Float32Array(totalLen)
    let off = 0
    for (const c of chunks) {
      merged.set(c, off)
      off += c.length
    }
    chunks = []
    if (!totalLen) return null
    const samples = resampleTo16k(merged, srcRate)
    return { blob: encodeWav(samples), samples, seconds: samples.length / TARGET_RATE }
  }

  /** 取消（上滑取消）：丢弃已采集数据 */
  function cancel() {
    if (!capturing) return
    capturing = false
    chunks = []
    teardown()
  }

  return { start, stop, cancel }
}

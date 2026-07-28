// ECAPA-TDNN 语种判断（浏览器端 ONNX 推理）：输入 16kHz Float32，输出中/英。
// 决定"按住说话"走接口 5b（英文对话）还是接口 16（中文翻译辅助）。
// 模型来自 ai-v2：public/models/ecapa_lang_id_int8.onnx（107 类，取 zh=106 / en=20）。
// 用 wasm-only 入口：默认入口是含 WebGPU/JSEP 的 bundle，会请求 jsep 变体的 wasm 运行时
import * as ort from 'onnxruntime-web/wasm'
// wasm 运行时用 Vite ?url 从 npm 包引入：dev 下可被动态 import（public/ 静态文件不行，
// Vite 会拦截 ?import 请求导致加载失败静默降级英文），build 时自动 emit 进产物
import ortWasmMjsUrl from 'onnxruntime-web/ort-wasm-simd-threaded.mjs?url'
import ortWasmUrl from 'onnxruntime-web/ort-wasm-simd-threaded.wasm?url'
import { toast } from '@/composables/useToast'

const MODEL_PATH = '/models/ecapa_lang_id_int8.onnx'
const ZH_IDX = 106
const EN_IDX = 20
const MAX_SAMPLES = 32000 // 2s @ 16kHz

// 指定 wasm 运行时文件路径，避免 CDN 版本漂移
ort.env.wasm.wasmPaths = { mjs: ortWasmMjsUrl, wasm: ortWasmUrl }
ort.env.wasm.numThreads = 1

let session: ort.InferenceSession | null = null
let initPromise: Promise<boolean> | null = null
let warned = false

async function ensureSession(): Promise<boolean> {
  if (session) return true
  if (!initPromise) {
    initPromise = ort.InferenceSession
      .create(MODEL_PATH, { executionProviders: ['wasm'] })
      .then((s) => {
        session = s
        return true
      })
      .catch((e) => {
        console.error('ECAPA model load failed', e)
        initPromise = null
        return false
      })
  }
  return initPromise
}

/** 提前加载模型（首次按住说话时调用），失败静默降级 */
export function preloadLangDetect() {
  void ensureSession()
}

/**
 * 判断语种；模型不可用时降级返回 'en'（走英文对话链路），并提示一次。
 * @param samples 16kHz mono Float32
 */
export async function detectLanguage(samples: Float32Array): Promise<'zh' | 'en'> {
  const ready = await ensureSession()
  if (!ready || !session) {
    if (!warned) {
      warned = true
      toast('语种模型加载失败，暂按英文处理')
    }
    return 'en'
  }
  try {
    const sliced = samples.length > MAX_SAMPLES ? samples.slice(0, MAX_SAMPLES) : samples
    const input = new ort.Tensor('float32', sliced, [1, sliced.length])
    const output = await session.run({ waveform: input })
    const logits = output.logits.data as Float32Array
    return logits[EN_IDX] > logits[ZH_IDX] ? 'en' : 'zh'
  } catch (e) {
    console.error('ECAPA detect failed', e)
    return 'en'
  }
}

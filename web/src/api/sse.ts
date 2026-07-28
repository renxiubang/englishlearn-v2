// POST-SSE 客户端：EventSource 不支持 POST，用 fetch + ReadableStream 手工解析。
// 后端约定：
//   - 建流前错误：响应 Content-Type 为 application/json，{code,message} 统一包裹（400/404/409/413）
//   - 建流后错误：以 `error` 事件下发 {code,message}，随后 done
//   - 事件帧格式：`event: X\ndata: {...}\n\n`（done 事件可无 data）
import type { ApiResponse } from '@/types'
import { ApiError } from './http'

const BASE_URL = '/api'

export type SseHandler = (event: string, data: Record<string, unknown>) => void

/** 发起 POST 并逐事件回调；error 事件转为 ApiError 抛出 */
export async function postSse(path: string, body: FormData, onEvent: SseHandler): Promise<void> {
  let res: Response
  try {
    res = await fetch(BASE_URL + path, { method: 'POST', body })
  } catch (e) {
    throw new ApiError(-1, e instanceof Error ? e.message : '网络异常')
  }

  const contentType = res.headers.get('Content-Type') ?? ''
  if (!contentType.includes('text/event-stream')) {
    // 建流前错误（或意外响应）：按统一 JSON 包裹解析
    let payload: ApiResponse<unknown> | null = null
    try {
      payload = await res.json()
    } catch {
      /* 保持 null */
    }
    throw new ApiError(payload?.code ?? res.status, payload?.message || '请求失败')
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (frame: string) => {
    let event = 'message'
    let dataRaw = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataRaw += line.slice(5).trim()
    }
    let data: Record<string, unknown> = {}
    if (dataRaw) {
      try {
        data = JSON.parse(dataRaw)
      } catch {
        /* 非 JSON data 忽略 */
      }
    }
    if (event === 'error') {
      throw new ApiError(Number(data.code ?? 500), String(data.message ?? '服务异常'))
    }
    onEvent(event, data)
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        if (frame.trim()) dispatch(frame)
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}

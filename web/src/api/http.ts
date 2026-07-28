import type { ApiResponse } from '@/types'

const BASE_URL = '/api'

export class ApiError extends Error {
  code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    // FormData 由浏览器自动设置 multipart 边界，不可手动指定 Content-Type
    const isForm = init?.body instanceof FormData
    res = await fetch(BASE_URL + path, {
      headers: isForm ? init?.headers : { 'Content-Type': 'application/json', ...init?.headers },
      ...init,
    })
  } catch (e) {
    throw new ApiError(-1, e instanceof Error ? e.message : '网络异常')
  }
  let body: ApiResponse<T>
  try {
    body = await res.json()
  } catch {
    throw new ApiError(res.status, '响应格式错误')
  }
  if (!res.ok || body.code !== 0) {
    throw new ApiError(body.code ?? res.status, body.message || '请求失败')
  }
  return body.data
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PUT', body: data === undefined ? undefined : JSON.stringify(data) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

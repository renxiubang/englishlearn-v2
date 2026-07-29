// fetch 封装：统一响应解包 { code, data, message }，自动注入 Bearer token，401 跳登录

import router from '@/router'

const TOKEN_KEY = 'admin_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  }
  if (init.body) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`/api${path}`, { ...init, headers })
  if (resp.status === 401 && !path.endsWith('/login')) {
    clearToken()
    router.push({ name: 'login' })
  }
  const body = await resp.json().catch(() => null)
  if (!body || typeof body.code !== 'number') {
    throw new ApiError(resp.status, `请求失败（HTTP ${resp.status}）`)
  }
  if (body.code !== 0) throw new ApiError(body.code, body.message ?? '请求失败')
  return body.data as T
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(data ?? {}) }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(data ?? {}) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

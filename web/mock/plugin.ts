/* =====================================================
 * 模拟后端服务（Vite dev 中间件，零额外依赖）
 * 仅保留后端尚未实现的接口（user / favorites / pic-story-progress / assist-hints / speech-score）；
 * contacts / chats / assist / pic-stories / categories 等已对接真实后端，未命中的请求经 next() 落到 vite proxy。
 * 统一响应格式：{ code, data, message }，模拟 100-300ms 延迟。
 * 数据存于内存，dev 服务运行期间持久；生产构建不参与打包。
 * ===================================================== */
import type { Plugin } from 'vite'
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  ASSIST_HINTS,
  SCORE_RANGES,
  USER_PROFILE,
  USER_STATS,
} from './data'

// ---------- 运行期状态（内存持久化） ----------
/** 收藏（id 自增） */
interface FavoriteRow { id: number; en: string; zh: string; createdAt: number }
const favorites: FavoriteRow[] = []
let favoriteSeq = 1
/** 看图讲故事进度：seed -> 最高分 */
const picStoryProgress: Record<string, number> = {}

// ---------- 工具 ----------
const delay = () => new Promise((r) => setTimeout(r, 100 + Math.random() * 200))

function send(res: ServerResponse, data: unknown, code = 0, message = 'ok', status = 200) {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify({ code, data, message }))
}

function notFound(res: ServerResponse) {
  send(res, null, 404, 'not found', 404)
}

function readBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolve) => {
    let raw = ''
    req.on('data', (chunk) => (raw += chunk))
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {})
      } catch {
        resolve({})
      }
    })
  })
}

function randomScore(type: string): number {
  const [base, span] = SCORE_RANGES[type] ?? [70, 30]
  return base + Math.floor(Math.random() * span)
}

// ---------- 路由处理 ----------
async function handle(req: IncomingMessage, res: ServerResponse): Promise<boolean> {
  const url = new URL(req.url ?? '/', 'http://localhost')
  const path = url.pathname
  const method = (req.method ?? 'GET').toUpperCase()

  // GET /api/user/profile
  if (method === 'GET' && path === '/api/user/profile') {
    send(res, USER_PROFILE)
    return true
  }
  // GET /api/user/stats
  if (method === 'GET' && path === '/api/user/stats') {
    send(res, USER_STATS)
    return true
  }

  // POST /api/speech/score（看图讲故事评分，后端未实现）
  if (method === 'POST' && path === '/api/speech/score') {
    const body = await readBody(req)
    const type = typeof body.type === 'string' ? body.type : 'assist'
    send(res, { score: randomScore(type) })
    return true
  }

  // GET /api/assist-hints?scene=
  if (method === 'GET' && path === '/api/assist-hints') {
    const scene = url.searchParams.get('scene') ?? 'chat'
    const hint = ASSIST_HINTS[scene]
    if (!hint) {
      notFound(res)
      return true
    }
    send(res, hint)
    return true
  }

  // GET|POST /api/favorites
  if (path === '/api/favorites') {
    if (method === 'GET') {
      send(res, favorites)
      return true
    }
    if (method === 'POST') {
      const body = await readBody(req)
      const en = typeof body.en === 'string' ? body.en.trim() : ''
      const zh = typeof body.zh === 'string' ? body.zh : ''
      if (!en) {
        send(res, null, 400, 'en is required', 400)
        return true
      }
      const exist = favorites.find((f) => f.en === en)
      if (exist) {
        send(res, exist)
        return true
      }
      const row: FavoriteRow = { id: favoriteSeq++, en, zh, createdAt: Date.now() }
      favorites.unshift(row)
      send(res, row)
      return true
    }
  }
  // DELETE /api/favorites/:id
  const favMatch = path.match(/^\/api\/favorites\/(\d+)$/)
  if (favMatch && method === 'DELETE') {
    const id = Number(favMatch[1])
    const idx = favorites.findIndex((f) => f.id === id)
    if (idx >= 0) favorites.splice(idx, 1)
    send(res, { removed: idx >= 0 })
    return true
  }

  // GET|PUT /api/pic-story-progress
  if (path === '/api/pic-story-progress') {
    if (method === 'GET') {
      send(res, picStoryProgress)
      return true
    }
    if (method === 'PUT') {
      const body = await readBody(req)
      const seed = typeof body.seed === 'string' ? body.seed : ''
      const score = typeof body.score === 'number' ? body.score : 0
      if (!seed) {
        send(res, null, 400, 'seed is required', 400)
        return true
      }
      if (!picStoryProgress[seed] || score > picStoryProgress[seed]) picStoryProgress[seed] = score
      send(res, picStoryProgress)
      return true
    }
  }

  return false
}

export function mockServerPlugin(): Plugin {
  return {
    name: 'mock-server',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url?.startsWith('/api/')) return next()
        delay()
          .then(() => handle(req, res))
          .then((handled) => {
            // 未命中的 /api/* 交给 vite proxy 转发到真实后端
            if (!handled) next()
          })
          .catch((err) => {
            send(res, null, 500, err instanceof Error ? err.message : 'server error', 500)
          })
      })
    },
  }
}

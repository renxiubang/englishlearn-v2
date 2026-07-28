// 按住说话全局跟踪：按下记录 Y 坐标，mousemove 上移超过 60px 进入取消态，
// 松开（含移出按钮后在文档任意处松开）统一结束并回调是否取消。
// 对应原型 beginTalkTracking / talkMove / endTalkTracking，触摸交互已按 PC 方案移除。
import { reactive, readonly } from 'vue'

const TALK_CANCEL_DIST = 60

const state = reactive({
  /** 是否正在按住说话 */
  active: false,
  /** 当前是否处于"上移取消"态 */
  cancel: false,
})

let startY = 0
let onEnd: ((cancelled: boolean) => void) | null = null

function handleMove(e: MouseEvent) {
  if (!state.active) return
  state.cancel = startY - e.clientY > TALK_CANCEL_DIST
}

function handleUp() {
  endTalk()
}

/** 开始一次按住说话跟踪；endCallback 在松开时回调（cancelled=是否上移取消） */
export function beginTalk(e: MouseEvent, endCallback: (cancelled: boolean) => void) {
  if (state.active) return
  state.active = true
  state.cancel = false
  startY = e.clientY
  onEnd = endCallback
  // 挂到 document：鼠标移出按钮后松开也能正确结束（原型中的全局 mouseup 兜底）
  document.addEventListener('mousemove', handleMove)
  document.addEventListener('mouseup', handleUp)
}

/** 强制结束当前跟踪（组件卸载等场景） */
export function endTalk() {
  if (!state.active) return
  document.removeEventListener('mousemove', handleMove)
  document.removeEventListener('mouseup', handleUp)
  const cancelled = state.cancel
  state.active = false
  state.cancel = false
  const cb = onEnd
  onEnd = null
  cb?.(cancelled)
}

export const talkState = readonly(state)

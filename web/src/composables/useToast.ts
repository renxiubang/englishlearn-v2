// 全局 Toast 服务：任意组件 import { toast } 即可弹出提示（对应原型 toast()）
import { reactive, readonly } from 'vue'

const state = reactive({
  message: '',
  visible: false,
})

let timer: ReturnType<typeof setTimeout> | null = null

export function toast(message: string) {
  state.message = message
  state.visible = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    state.visible = false
    timer = null
  }, 1600)
}

export const toastState = readonly(state)

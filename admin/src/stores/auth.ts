import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import { clearToken, getToken, setToken } from '@/api/http'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())

  async function login(password: string): Promise<void> {
    const data = await authApi.login(password)
    token.value = data.token
    setToken(data.token)
  }

  function logout(): void {
    token.value = ''
    clearToken()
  }

  return { token, login, logout }
})

/**
 * 登录状态（模块级单例，所有组件共享同一份 ref）。
 *
 * 不引入 Pinia：当前只有"当前用户"一份全局状态，一个模块级 ref 就够，
 * 少一层依赖也少一处需要配置的东西。
 */

import { computed, ref } from 'vue'
import { ApiError, api, setUnauthorizedHandler } from '../api/client'

export type AuthUser = {
  id: number
  email: string
  display_name: string
  role: string
}

const user = ref<AuthUser | null>(null)
const bootstrapping = ref(true)
const loggingIn = ref(false)
const loginError = ref('')

const isAuthenticated = computed(() => user.value !== null)

// 业务接口返回 401 时统一回到登录态；故事板内容由调用方保留。
setUnauthorizedHandler(() => {
  user.value = null
})

async function bootstrap(): Promise<void> {
  bootstrapping.value = true
  try {
    const data = await api.get<{ user: AuthUser }>('/api/v1/auth/me')
    user.value = data.user
  } catch (error) {
    // 401 是正常的"未登录"，其余错误也当作未登录处理，并留在登录页。
    user.value = null
    if (!(error instanceof ApiError && error.status === 401)) {
      loginError.value = error instanceof Error ? error.message : ''
    }
  } finally {
    bootstrapping.value = false
  }
}

async function login(email: string, password: string, remember: boolean): Promise<boolean> {
  if (loggingIn.value) return false
  loggingIn.value = true
  loginError.value = ''
  try {
    const data = await api.post<{ user: AuthUser }>('/api/v1/auth/login', {
      email,
      password,
      remember,
    })
    user.value = data.user
    return true
  } catch (error) {
    loginError.value = error instanceof Error ? error.message : '登录失败，请稍后重试'
    return false
  } finally {
    loggingIn.value = false
  }
}

async function logout(): Promise<void> {
  try {
    await api.post('/api/v1/auth/logout')
  } catch {
    /* 会话可能已经失效，本地照样清干净 */
  } finally {
    user.value = null
  }
}

export function useAuth() {
  return {
    user,
    isAuthenticated,
    bootstrapping,
    loggingIn,
    loginError,
    login,
    logout,
    bootstrap,
  }
}

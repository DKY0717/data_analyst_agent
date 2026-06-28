import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { demoLogin as requestDemoLogin, fetchCurrentUser } from '@/api/agent'

const TOKEN_KEY = 'daa_auth_token'
const USER_KEY = 'daa_auth_user'

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref(loadUser())
  const selectedRole = ref(user.value?.roles?.[0] || 'guest')
  const loading = ref(false)
  const error = ref(null)

  const isAuthenticated = computed(() => Boolean(token.value && user.value))
  const currentRole = computed(() => user.value?.roles?.[0] || 'guest')
  const authHeaders = computed(() => {
    if (!token.value) return {}
    return { Authorization: `Bearer ${token.value}` }
  })

  function persist(nextToken, nextUser) {
    token.value = nextToken
    user.value = nextUser
    selectedRole.value = nextUser?.roles?.[0] || 'guest'
    localStorage.setItem(TOKEN_KEY, nextToken)
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
  }

  async function demoLogin(role) {
    loading.value = true
    error.value = null
    try {
      const data = await requestDemoLogin(role)
      // 前端只保存后端签发的 token，不接触 JWT_SECRET，避免演示代码变成密钥泄漏点。
      persist(data.access_token, data.user)
      return data
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadMe() {
    if (!token.value) return null
    const currentUser = await fetchCurrentUser()
    // 刷新身份只更新最小用户摘要，token 仍由后端签发和前端本地保存。
    user.value = currentUser
    selectedRole.value = currentUser?.roles?.[0] || 'guest'
    localStorage.setItem(USER_KEY, JSON.stringify(currentUser))
    return currentUser
  }

  function logout() {
    token.value = ''
    user.value = null
    selectedRole.value = 'guest'
    error.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    user,
    selectedRole,
    loading,
    error,
    isAuthenticated,
    currentRole,
    authHeaders,
    demoLogin,
    loadMe,
    logout,
  }
})

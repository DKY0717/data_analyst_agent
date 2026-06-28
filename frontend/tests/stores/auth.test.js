import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/agent', () => ({
  demoLogin: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('初始状态为未认证', () => {
    const store = useAuthStore()

    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.authHeaders).toEqual({})
    expect(store.currentRole).toBe('guest')
  })

  it('从 localStorage 恢复演示身份', () => {
    localStorage.setItem('daa_auth_token', 'token-123')
    localStorage.setItem(
      'daa_auth_user',
      JSON.stringify({ user_id: 'demo:analyst', auth_method: 'jwt', roles: ['analyst'] }),
    )

    const store = useAuthStore()

    expect(store.token).toBe('token-123')
    expect(store.user.user_id).toBe('demo:analyst')
    expect(store.currentRole).toBe('analyst')
  })

  it('demoLogin 保存 token 和 user', async () => {
    const { demoLogin } = await import('@/api/agent')
    demoLogin.mockResolvedValue({
      access_token: 'token-abc',
      user: { user_id: 'demo:support', auth_method: 'jwt', roles: ['support'] },
    })
    const store = useAuthStore()

    await store.demoLogin('support')

    expect(store.token).toBe('token-abc')
    expect(store.selectedRole).toBe('support')
    expect(store.authHeaders).toEqual({ Authorization: 'Bearer token-abc' })
    expect(JSON.parse(localStorage.getItem('daa_auth_user')).roles).toEqual(['support'])
  })

  it('logout 清理身份状态和本地缓存', () => {
    localStorage.setItem('daa_auth_token', 'token-abc')
    localStorage.setItem(
      'daa_auth_user',
      JSON.stringify({ user_id: 'demo:admin', auth_method: 'jwt', roles: ['admin'] }),
    )
    const store = useAuthStore()

    store.logout()

    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(store.error).toBeNull()
    expect(localStorage.getItem('daa_auth_token')).toBeNull()
    expect(localStorage.getItem('daa_auth_user')).toBeNull()
  })
})

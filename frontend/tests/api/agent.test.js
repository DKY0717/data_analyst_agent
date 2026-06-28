import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const post = vi.fn()
const get = vi.fn()
const requestUse = vi.fn()

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get,
      post,
      interceptors: {
        request: { use: requestUse },
      },
    })),
  },
}))

describe('agent api auth behavior', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    setActivePinia(createPinia())
    localStorage.clear()
    global.fetch = vi.fn()
  })

  it('demoLogin unwraps SuccessResponse data', async () => {
    const { demoLogin } = await import('@/api/agent')
    post.mockResolvedValue({ data: { data: { access_token: 'token-1', user: { roles: ['admin'] } } } })

    const result = await demoLogin('admin')

    expect(post).toHaveBeenCalledWith('/auth/demo-login', { role: 'admin' })
    expect(result.access_token).toBe('token-1')
  })

  it('axios interceptor attaches Authorization when token exists', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    await import('@/api/agent')
    const interceptor = requestUse.mock.calls[0][0]
    const auth = useAuthStore()
    auth.token = 'token-axios'

    const config = interceptor({ headers: {} })

    expect(config.headers.Authorization).toBe('Bearer token-axios')
  })

  it('queryAgentSSE sends Authorization header', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const auth = useAuthStore()
    auth.token = 'token-sse'
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"type":"result","data":{"answer":"ok"}}\n\n'))
        controller.close()
      },
    })
    fetch.mockResolvedValue({ ok: true, body: stream })
    const { queryAgentSSE } = await import('@/api/agent')

    await queryAgentSSE('统计销售额', 'session-1', vi.fn())

    expect(fetch).toHaveBeenCalledWith('/api/chat/query/stream', expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: 'Bearer token-sse',
        'Content-Type': 'application/json',
      }),
    }))
  })

  it('queryAgentSSE normalizes 401 error', async () => {
    fetch.mockResolvedValue({ ok: false, status: 401, statusText: 'Unauthorized' })
    const { queryAgentSSE } = await import('@/api/agent')

    await expect(queryAgentSSE('统计销售额', 'session-1', vi.fn())).rejects.toThrow('需要登录后才能查询')
  })

  it('exports permission demo questions', async () => {
    const { permissionDemoQuestions } = await import('@/api/agent')

    expect(permissionDemoQuestions.map(item => item.role)).toEqual(['analyst', 'analyst', 'support', 'admin'])
    expect(permissionDemoQuestions[1].expected).toContain('阻断')
  })
})

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useQueryStore } from '@/stores/query'

vi.mock('@/api/agent', () => ({
  queryAgent: vi.fn(),
  queryAgentSSE: vi.fn(),
  fetchSchema: vi.fn(() => Promise.resolve([])),
}))

describe('useQueryStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态正确', () => {
    const store = useQueryStore()
    expect(store.question).toBe('')
    expect(store.loading).toBe(false)
    expect(store.result).toBeNull()
    expect(store.error).toBeNull()
    expect(store.history).toEqual([])
    expect(store.favorites).toEqual([])
    expect(store.useStreaming).toBe(true)
  })

  it('setQuestion 更新问题', () => {
    const store = useQueryStore()
    store.setQuestion('测试问题')
    expect(store.question).toBe('测试问题')
  })

  it('toggleFavorite 添加收藏', () => {
    const store = useQueryStore()
    store.toggleFavorite({ question: '测试问题', answer: '答案' })
    expect(store.favorites).toHaveLength(1)
    expect(store.favorites[0].question).toBe('测试问题')
    expect(store.isFavorite('测试问题')).toBe(true)
  })

  it('toggleFavorite 移除收藏', () => {
    const store = useQueryStore()
    store.toggleFavorite({ question: '测试问题' })
    expect(store.favorites).toHaveLength(1)
    store.toggleFavorite({ question: '测试问题' })
    expect(store.favorites).toHaveLength(0)
    expect(store.isFavorite('测试问题')).toBe(false)
  })

  it('removeFavorite 删除指定收藏', () => {
    const store = useQueryStore()
    store.toggleFavorite({ question: '问题1' })
    store.toggleFavorite({ question: '问题2' })
    store.removeFavorite('问题1')
    expect(store.favorites).toHaveLength(1)
    expect(store.favorites[0].question).toBe('问题2')
  })

  it('favorites 持久化到 localStorage', () => {
    const store = useQueryStore()
    store.toggleFavorite({ question: '持久化测试' })

    const saved = JSON.parse(localStorage.getItem('daa_favorites') || '[]')
    expect(saved).toHaveLength(1)
    expect(saved[0].question).toBe('持久化测试')
  })

  it('clearResult 清除结果和错误', () => {
    const store = useQueryStore()
    store.result = { answer: 'test' }
    store.error = new Error('test')
    store.clearResult()
    expect(store.result).toBeNull()
    expect(store.error).toBeNull()
  })

  it('hasResult 和 hasRows 计算属性', () => {
    const store = useQueryStore()
    expect(store.hasResult).toBe(false)
    expect(store.hasRows).toBe(false)

    store.result = { columns: ['a'], rows: [] }
    expect(store.hasResult).toBe(true)
    expect(store.hasRows).toBe(false)

    store.result = { columns: ['a'], rows: [[1]] }
    expect(store.hasRows).toBe(true)
  })

  it('submitQuestion 空问题不执行', async () => {
    const store = useQueryStore()
    await store.submitQuestion('')
    expect(store.loading).toBe(false)
  })

  it('submitQuestion 防止重复提交', async () => {
    const store = useQueryStore()
    store.loading = true
    await store.submitQuestion('问题')
    expect(store.loading).toBe(true)
  })

  it('cancelQuery 无 abortController 时不报错', () => {
    const store = useQueryStore()
    expect(() => store.cancelQuery()).not.toThrow()
  })

  it('cancelQuery 中断进行中的请求', async () => {
    const { queryAgentSSE } = await import('@/api/agent')
    let rejectFn
    queryAgentSSE.mockImplementation((_q, _s, _onProgress, signal) => {
      return new Promise((_, reject) => {
        rejectFn = reject
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })
    })

    const store = useQueryStore()
    store.question = '测试取消'
    const p = store.submitQuestion()
    await new Promise(r => setTimeout(r, 50))
    store.cancelQuery()
    await p
    expect(store.loading).toBe(false)
  })
})

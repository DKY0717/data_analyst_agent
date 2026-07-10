import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { shallowMount } from '@vue/test-utils'

import Home from '@/views/Home.vue'
import AnswerPanel from '@/components/AnswerPanel.vue'
import IntentPanel from '@/components/IntentPanel.vue'
import OptimizationPanel from '@/components/OptimizationPanel.vue'
import SQLPanel from '@/components/SQLPanel.vue'
import { useQueryStore } from '@/stores/query'
import queryResponse from '../fixtures/query_response.json'

vi.mock('@/api/agent', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchSchema: vi.fn(() => Promise.resolve([])),
    queryAgent: vi.fn(),
    queryAgentSSE: vi.fn(),
  }
})

async function mountHome() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Home },
      { path: '/query/:question', name: 'query', component: Home },
    ],
  })
  await router.push('/')
  await router.isReady()

  const store = useQueryStore()
  // 前端行为测试与后端 Pydantic 测试共享同一份 fixture。
  store.result = structuredClone(queryResponse)
  const wrapper = shallowMount(Home, {
    global: {
      plugins: [pinia, router],
      stubs: {
        'el-tag': true,
        'el-switch': true,
      },
    },
  })
  await nextTick()
  return { store, wrapper }
}

describe('Home QueryResponse contract', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('passes the current backend response fields to detail panels', async () => {
    const { wrapper } = await mountHome()

    expect(wrapper.findComponent(SQLPanel).props('sql')).toContain('SUM(total_amount)')
    expect(wrapper.findComponent(IntentPanel).props('intent').metrics[0].concept).toBe('sales_amount')
    expect(wrapper.findComponent(OptimizationPanel).props('result')).toMatchObject({
      execution_time_ms: 18,
      retry_count: 1,
      optimization_suggestions: ['避免 SELECT *'],
    })
    expect(wrapper.findComponent(AnswerPanel).props('executionMetrics')).toEqual({
      row_count: 1,
      total_latency_ms: 18,
      llm_call_count: 2,
    })
  })

  it('forwards a clarification option without changing its shape', async () => {
    const { store, wrapper } = await mountHome()
    const submitClarification = vi.spyOn(store, 'submitClarification').mockResolvedValue()
    const option = { candidate_id: 'metric_sales', label: '销售额' }

    wrapper.findComponent(IntentPanel).vm.$emit('clarify', option)
    await nextTick()

    expect(submitClarification).toHaveBeenCalledWith(option)
  })
})

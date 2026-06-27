import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AnswerPanel from '@/components/AnswerPanel.vue'

describe('AnswerPanel', () => {
  it('显示空状态', () => {
    const wrapper = mount(AnswerPanel)
    expect(wrapper.text()).toContain('从一个业务问题开始')
  })

  it('显示加载骨架屏', () => {
    const wrapper = mount(AnswerPanel, {
      props: { loading: true, loadingStage: '正在解析意图...' },
    })
    expect(wrapper.find('.skeleton-group').exists()).toBe(true)
    expect(wrapper.text()).toContain('正在解析意图...')
  })

  it('显示错误信息', () => {
    const wrapper = mount(AnswerPanel, {
      props: { error: { message: '网络超时' } },
    })
    expect(wrapper.text()).toContain('分析失败')
    expect(wrapper.text()).toContain('网络超时')
  })

  it('渲染 Markdown 答案', () => {
    const wrapper = mount(AnswerPanel, {
      props: { answer: '**加粗文本** 和 `代码`' },
    })
    expect(wrapper.find('.markdown-body').exists()).toBe(true)
    expect(wrapper.html()).toContain('<strong>加粗文本</strong>')
    expect(wrapper.html()).toContain('<code>代码</code>')
  })

  it('显示执行指标', () => {
    const wrapper = mount(AnswerPanel, {
      props: {
        answer: '测试答案',
        executionMetrics: {
          row_count: 42,
          total_latency_ms: 120,
          llm_call_count: 2,
        },
      },
    })
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('120ms')
    expect(wrapper.text()).toContain('2')
  })
})
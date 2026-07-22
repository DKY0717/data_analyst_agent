import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import OptimizationPanel from '@/components/OptimizationPanel.vue'

describe('OptimizationPanel', () => {
  it('renders execution metrics and suggestions from QueryResponse', () => {
    // 优化信息属于 QueryResponse 顶层，测试防止组件再次误读 audit_report。
    const wrapper = mount(OptimizationPanel, {
      props: {
        result: {
          execution_time_ms: 23,
          retry_count: 2,
          optimization_suggestions: ['增加时间过滤条件'],
        },
      },
    })

    expect(wrapper.text()).toContain('23ms')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('增加时间过滤条件')
  })
})

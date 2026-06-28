import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AuditPanel from '@/components/AuditPanel.vue'

function mountPanel(report) {
  return mount(AuditPanel, {
    props: { report },
    global: {
      stubs: {
        'el-tag': { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('AuditPanel', () => {
  it('展示身份摘要', () => {
    const wrapper = mountPanel({
      user_id: 'demo:analyst',
      auth_method: 'jwt',
      roles: ['analyst'],
      is_sql_safe: true,
      execution_success: true,
      limit_injected: true,
      blocked_rules: [],
      events: [],
    })

    expect(wrapper.text()).toContain('demo:analyst')
    expect(wrapper.text()).toContain('jwt')
    expect(wrapper.text()).toContain('analyst')
  })

  it('高亮 authorization blocked 事件和阻断规则', () => {
    const wrapper = mountPanel({
      user_id: 'demo:analyst',
      auth_method: 'jwt',
      roles: ['analyst'],
      is_sql_safe: true,
      execution_success: false,
      limit_injected: false,
      blocked_rules: ['block_unauthorized_column:customers.customer_name'],
      events: [
        {
          stage: 'authorization',
          action: 'authorize_sql',
          status: 'blocked',
          message: '角色 analyst 无权访问 customers.customer_name',
          rule_id: 'block_unauthorized_column',
        },
      ],
    })

    expect(wrapper.text()).toContain('authorization')
    expect(wrapper.text()).toContain('authorize_sql')
    expect(wrapper.text()).toContain('block_unauthorized_column')
    expect(wrapper.find('.audit-event--authorization').exists()).toBe(true)
  })
})

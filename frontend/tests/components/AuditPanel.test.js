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

  it('展示允许查询的行级过滤权限摘要', () => {
    const wrapper = mountPanel({
      user_id: 'demo:analyst',
      auth_method: 'jwt',
      roles: ['analyst'],
      is_sql_safe: true,
      execution_success: true,
      limit_injected: false,
      blocked_rules: [],
      permission_observability: {
        permission_checked: true,
        allowed: true,
        blocked_rule: null,
        referenced_tables: ['orders'],
        referenced_columns: ['orders.total_amount'],
        row_filters_applied: [{ table: 'orders', rule_id: 'row_filter_region_scope' }],
        authorized_sql_changed: true,
      },
      events: [],
    })

    expect(wrapper.text()).toContain('数据权限')
    expect(wrapper.text()).toContain('已检查')
    expect(wrapper.text()).toContain('允许')
    expect(wrapper.text()).toContain('已改写')
    expect(wrapper.text()).toContain('orders')
    expect(wrapper.text()).toContain('orders.total_amount')
    expect(wrapper.text()).toContain('row_filter_region_scope')
  })

  it('展示阻断查询的权限规则和引用字段', () => {
    const wrapper = mountPanel({
      user_id: 'demo:analyst',
      auth_method: 'jwt',
      roles: ['analyst'],
      is_sql_safe: true,
      execution_success: false,
      limit_injected: false,
      blocked_rules: ['block_unauthorized_column:customers.customer_name'],
      permission_observability: {
        permission_checked: true,
        allowed: false,
        blocked_rule: 'block_unauthorized_column',
        referenced_tables: ['customers'],
        referenced_columns: ['customers.customer_name'],
        row_filters_applied: [],
        authorized_sql_changed: false,
      },
      events: [],
    })

    expect(wrapper.text()).toContain('阻断')
    expect(wrapper.text()).toContain('block_unauthorized_column')
    expect(wrapper.text()).toContain('customers')
    expect(wrapper.text()).toContain('customers.customer_name')
  })

  it('兼容缺省权限摘要', () => {
    const wrapper = mountPanel({
      user_id: 'anonymous',
      auth_method: 'none',
      roles: ['guest'],
      is_sql_safe: true,
      execution_success: true,
      limit_injected: false,
      blocked_rules: [],
      events: [],
    })

    expect(wrapper.text()).toContain('数据权限')
    expect(wrapper.text()).toContain('未触发权限检查')
  })
})

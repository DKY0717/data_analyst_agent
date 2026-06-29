import { test, expect } from '@playwright/test'

let currentRole = 'guest'

const schemaResponse = {
  code: 200,
  message: 'success',
  data: {
    tables: {
      orders: { columns: [{ name: 'order_id' }, { name: 'total_amount' }] },
      customers: { columns: [{ name: 'customer_name' }, { name: 'registered_at' }] },
    },
  },
}

function userForRole(role) {
  if (role === 'admin') return { user_id: 'demo:admin', auth_method: 'jwt', roles: ['admin'] }
  if (role === 'analyst') return { user_id: 'demo:analyst', auth_method: 'jwt', roles: ['analyst'] }
  return { user_id: 'anonymous', auth_method: 'none', roles: ['guest'] }
}

function successResult(user, answer, columns, rows) {
  return {
    question: '',
    session_id: 'e2e-session',
    status: 'completed',
    answer,
    sql: 'SELECT 1',
    generated_sql: 'SELECT 1',
    optimized_sql: 'SELECT 1',
    columns,
    rows,
    is_sql_safe: true,
    execution_time_ms: 12,
    retry_count: 0,
    audit_report: {
      user_id: user.user_id,
      auth_method: user.auth_method,
      roles: user.roles,
      is_sql_safe: true,
      execution_success: true,
      limit_injected: false,
      blocked_rules: [],
      execution_metrics: { row_count: rows.length, total_latency_ms: 120, llm_call_count: 0 },
      events: [
        {
          stage: 'authorization',
          action: 'authorize_sql',
          status: 'success',
          message: `角色 ${user.roles[0]} 通过数据权限检查`,
          rule_id: null,
        },
      ],
    },
  }
}

function salesResult(user) {
  return successResult(
    user,
    '2024 年每个月销售额已统计完成。',
    ['month', 'sales'],
    [['2024-01', 128000], ['2024-02', 136000]],
  )
}

function adminCustomerResult(user) {
  return successResult(
    user,
    '管理员已成功查询客户姓名和注册日期。',
    ['customer_name', 'registered_at'],
    [['张三', '2024-01-03']],
  )
}

function blockedResult(user) {
  return {
    question: '列出客户姓名和注册日期',
    session_id: 'e2e-session',
    status: 'blocked',
    answer: '请求已被数据权限策略阻断：analyst 不能访问 customers.customer_name。',
    sql: '',
    generated_sql: '',
    optimized_sql: '',
    columns: [],
    rows: [],
    is_sql_safe: true,
    execution_time_ms: 0,
    retry_count: 0,
    audit_report: {
      user_id: user.user_id,
      auth_method: user.auth_method,
      roles: user.roles,
      is_sql_safe: true,
      execution_success: false,
      limit_injected: false,
      blocked_rules: ['block_unauthorized_column:customers.customer_name'],
      execution_metrics: { row_count: 0, total_latency_ms: 30, llm_call_count: 0 },
      events: [
        {
          stage: 'authorization',
          action: 'authorize_sql',
          status: 'blocked',
          message: '角色 analyst 无权访问 customers.customer_name',
          rule_id: 'block_unauthorized_column',
        },
      ],
    },
  }
}

function resultForQuestion(question) {
  const user = userForRole(currentRole)
  if (question.includes('客户姓名') && currentRole === 'analyst') return blockedResult(user)
  if (question.includes('客户姓名') && currentRole === 'admin') return adminCustomerResult(user)
  return salesResult(user)
}

function toSse(result) {
  return [
    'data: {"type":"progress","stage":"权限检查","progress":60}\n\n',
    `data: ${JSON.stringify({ type: 'result', data: result })}\n\n`,
    'data: [DONE]\n\n',
  ].join('')
}

async function mockBackend(page) {
  currentRole = 'guest'

  await page.route('**/api/schema', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(schemaResponse),
    })
  })

  await page.route('**/api/auth/demo-login', async route => {
    const body = route.request().postDataJSON()
    currentRole = body.role
    const user = userForRole(currentRole)

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        message: 'demo login success',
        data: {
          access_token: `mock-token-${currentRole}`,
          token_type: 'bearer',
          expires_in: 86400,
          user,
        },
      }),
    })
  })

  await page.route('**/api/auth/me', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(userForRole(currentRole)),
    })
  })

  await page.route('**/api/chat/query/stream', async route => {
    const body = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: toSse(resultForQuestion(body.question)),
    })
  })

  await page.route('**/api/chat/query', async route => {
    const body = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ code: 200, message: 'success', data: resultForQuestion(body.question) }),
    })
  })
}

async function submitQuestion(page, question) {
  await page.locator('.query-card textarea').fill(question)
  await page.locator('.submit-button').click()
}

test.describe('Permission Demo E2E', () => {
  test.beforeEach(async ({ page }) => {
    await mockBackend(page)
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('analyst blocked flow and admin success flow are demonstrable', async ({ page }) => {
    await expect(page.locator('.auth-bar')).toContainText('未认证')

    await page.locator('[data-test="role-analyst"]').click()
    await expect(page.locator('.auth-bar')).toContainText('demo:analyst')
    await expect(page.locator('.auth-bar')).toContainText('jwt')
    await expect(page.locator('.auth-bar')).toContainText('analyst')

    await submitQuestion(page, '统计 2024 年每个月的销售额')
    await expect(page.locator('.answer-panel')).toContainText('2024 年每个月销售额已统计完成。')

    await submitQuestion(page, '列出客户姓名和注册日期')
    await expect(page.locator('.answer-panel')).toContainText('请求已被数据权限策略阻断')
    await expect(page.locator('.audit-panel')).toContainText('demo:analyst')
    await expect(page.locator('.audit-panel')).toContainText('jwt')
    await expect(page.locator('.audit-panel')).toContainText('analyst')
    await expect(page.locator('.audit-panel')).toContainText('authorization')
    await expect(page.locator('.audit-panel')).toContainText('block_unauthorized_column')
    await expect(page.locator('.audit-panel')).toContainText('block_unauthorized_column:customers.customer_name')

    await page.locator('[data-test="role-admin"]').click()
    await expect(page.locator('.auth-bar')).toContainText('demo:admin')

    await submitQuestion(page, '列出客户姓名和注册日期')
    await expect(page.locator('.answer-panel')).toContainText('管理员已成功查询客户姓名和注册日期。')
    await expect(page.locator('.audit-panel')).toContainText('demo:admin')
    await expect(page.locator('.audit-panel')).toContainText('authorization')
  })
})

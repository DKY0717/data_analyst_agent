import { test, expect } from '@playwright/test'

test.describe('Data Analyst Agent - 页面基础', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('页面标题和品牌标识', async ({ page }) => {
    await expect(page.locator('.topbar-brand h1')).toHaveText('Data Analyst Agent')
    await expect(page.locator('.topbar-logo')).toHaveText('⚡')
  })

  test('左侧栏包含输入框、示例问题、历史面板、Schema 面板', async ({ page }) => {
    await expect(page.locator('.query-card')).toBeVisible()
    const panels = page.locator('.left-column .compact-panel')
    await expect(panels.nth(0).locator('.chip-list')).toBeVisible()
    await expect(panels.nth(2)).toBeVisible()
  })

  test('普通示例问题展示 12 条，权限演示问题展示 4 条', async ({ page }) => {
    const panels = page.locator('.left-column .compact-panel')
    await expect(panels.nth(0).locator('.question-chip')).toHaveCount(12)
    await expect(panels.nth(1).locator('.question-chip')).toHaveCount(4)
  })

  test('初始状态显示空结果提示', async ({ page }) => {
    await expect(page.locator('.empty-state')).toBeVisible()
    await expect(page.locator('.empty-state h3')).toHaveText('从一个业务问题开始')
  })

  test('顶栏显示数据库连接状态', async ({ page }) => {
    const tag = page.locator('.status-group .el-tag').first()
    await expect(tag).toBeVisible()
  })

  test('暗色模式切换', async ({ page }) => {
    const themeToggle = page.locator('.theme-toggle')
    await expect(themeToggle).toBeVisible()

    const initialTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    )

    await themeToggle.click()
    await page.waitForTimeout(300)

    const newTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    )
    expect(newTheme).not.toBe(initialTheme)
  })
})

test.describe('Data Analyst Agent - 查询流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('点击示例问题自动填入输入框', async ({ page }) => {
    const firstChip = page.locator('.question-chip').first()

    await firstChip.click()

    const textarea = page.locator('.query-card textarea')
    const value = await textarea.inputValue()
    expect(value.trim().length).toBeGreaterThan(0)
  })

  test('输入问题后按钮可点击', async ({ page }) => {
    const textarea = page.locator('.query-card textarea')
    await textarea.fill('统计 2024 年每个月的销售额')

    const submitBtn = page.locator('.submit-button')
    await expect(submitBtn).toBeEnabled()
  })

  test('空输入时按钮禁用', async ({ page }) => {
    const textarea = page.locator('.query-card textarea')
    await textarea.fill('')

    const submitBtn = page.locator('.submit-button')
    await expect(submitBtn).toBeDisabled()
  })

  test('提交查询后显示加载状态', async ({ page }) => {
    // 加载态测试使用可控慢响应，避免本地认证或真实 LLM 状态影响 UI 断言。
    await page.route('**/api/chat/query/stream', async route => {
      await new Promise(resolve => setTimeout(resolve, 1500))
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"type":"progress","stage":"生成 SQL","progress":65}\n\n',
      })
    })
    const textarea = page.locator('.query-card textarea')
    await textarea.fill('统计 2024 年每个月的销售额')

    await page.locator('.submit-button').click()

    await expect(page.locator('.progress-bar-wrap')).toBeVisible({ timeout: 3000 })
    await expect(page.locator('.cancel-btn')).toBeVisible()
  })

  test('SSE 模式切换开关', async ({ page }) => {
    const switchEl = page.locator('.stream-switch')
    await expect(switchEl).toBeVisible()

    const label = page.locator('.stream-switch .el-switch__label')
    await expect(label.first()).toBeVisible()
  })
})

test.describe('Data Analyst Agent - 路由', () => {
  test('根路径正常加载', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.topbar-brand h1')).toBeVisible()
  })

  test('带问题参数的路由', async ({ page }) => {
    await page.goto('/query/统计2024年每月销售额')
    await page.waitForLoadState('domcontentloaded')

    const textarea = page.locator('.query-card textarea')
    await expect(textarea).toHaveValue('统计2024年每月销售额', { timeout: 10000 })
  })
})

test.describe('Data Analyst Agent - 响应式布局', () => {
  test('桌面端三列布局', async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const grid = page.locator('.workbench-grid')
    await expect(grid).toBeVisible()
  })

  test('平板端两列布局', async ({ page }) => {
    await page.setViewportSize({ width: 1000, height: 768 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.topbar-brand h1')).toBeVisible()
  })

  test('移动端单列布局', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.topbar-brand h1')).toBeVisible()
    await expect(page.locator('.query-card')).toBeVisible()
  })
})

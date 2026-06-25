import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  // 一次 Agent 查询可能包含生成、修复和答案生成等多次 LLM 调用，前端超时需覆盖完整链路。
  timeout: 120000,
})

export const exampleQuestions = [
  '统计 2024 年每个月的销售额',
  '找出销售额最高的前 10 个商品',
  '分析各商品类别的退款率',
  '统计不同地区的客户数量',
  '分析 2024 年用户复购率',
]

const TABLE_LABELS = {
  regions: '地区表',
  customers: '用户表',
  categories: '类别表',
  products: '商品表',
  orders: '订单表',
  order_items: '订单明细',
  payments: '支付表',
  refunds: '退款表',
}

export async function fetchSchema() {
  const response = await client.get('/schema')
  const tables = response.data.data.tables
  return Object.entries(tables).map(([name, info]) => ({
    name,
    label: TABLE_LABELS[name] || name,
    fields: info.columns.map((col) => col.name),
  }))
}

export function createMockResult(question, sessionId) {
  // 开发环境后端不可用时，用同一份响应结构预览 UI，避免前端和 API 契约脱节。
  return {
    question,
    session_id: sessionId,
    sql: `SELECT
  strftime(order_date, '%Y-%m') AS month,
  SUM(total_amount) AS sales
FROM orders
WHERE order_date >= DATE '2024-01-01'
  AND order_date < DATE '2025-01-01'
GROUP BY month
ORDER BY month
LIMIT 1000;`,
    is_sql_safe: true,
    columns: ['month', 'sales'],
    rows: [
      ['2024-01', 12840.5],
      ['2024-02', 14520.8],
      ['2024-03', 16890.3],
      ['2024-04', 15330.2],
      ['2024-05', 18110.7],
      ['2024-06', 19780.4],
    ],
    answer: '查询结果显示，2024 年上半年销售额整体呈上升趋势，其中 6 月销售额最高，达到 19780.4 元。',
    status: 'completed',
    execution_time_ms: 42,
    retry_count: 0,
    optimization_suggestions: ['当前查询已按月份聚合，建议关注 DuckDB 对订单日期过滤和聚合的执行计划。'],
    audit_report: {
      question,
      final_sql: `SELECT strftime(order_date, '%Y-%m') AS month, SUM(total_amount) AS sales FROM orders LIMIT 1000`,
      is_sql_safe: true,
      execution_success: true,
      retry_count: 0,
      limit_injected: true,
      blocked_rules: [],
      events: [
        {
          stage: 'generation',
          action: 'generate_sql',
          status: 'success',
          message: 'LLM 已生成 SQL',
          rule_id: null,
          details: {},
        },
        {
          stage: 'guard',
          action: 'inject_limit',
          status: 'success',
          message: '查询缺少 LIMIT，已自动注入 LIMIT 1000',
          rule_id: 'limit_injected',
          details: { limit_injected: true, max_rows: 1000 },
        },
        {
          stage: 'execution',
          action: 'execute_sql',
          status: 'success',
          message: 'SQL 执行成功',
          rule_id: null,
          details: { execution_time_ms: 42, row_count: 6 },
        },
      ],
    },
    used_mock: true,
  }
}

export async function queryAgent(question, sessionId, clarification = null) {
  try {
    const payload = { question, session_id: sessionId }
    if (clarification) {
      payload.clarification_id = clarification.clarificationId
      payload.clarification_candidate_id = clarification.candidateId
      payload.clarification_text = clarification.text || null
    }
    const response = await client.post('/chat/query', payload)
    // 后端返回 { code, message, data: { question, sql, rows, ... } }
    // 提取嵌套的 data 字段，与前端组件期望的结构对齐
    return { ...response.data.data, used_mock: false }
  } catch (error) {
    // 只允许开发环境使用 mock；生产环境必须暴露真实接口错误，避免把故障伪装成成功结果。
    if (import.meta.env.DEV) return createMockResult(question, sessionId)
    throw error
  }
}

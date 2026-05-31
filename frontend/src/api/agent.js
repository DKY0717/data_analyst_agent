import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const exampleQuestions = [
  '统计 2024 年每个月的销售额',
  '找出销售额最高的前 10 个商品',
  '分析各商品类别的退款率',
  '统计不同地区的客户数量',
  '分析 2024 年用户复购率',
]

export const schemaTables = [
  { name: 'regions', label: '地区表', fields: ['region_id', 'region_name', 'province', 'city'] },
  { name: 'customers', label: '用户表', fields: ['customer_id', 'gender', 'age', 'region_id'] },
  { name: 'categories', label: '类别表', fields: ['category_id', 'category_name'] },
  { name: 'products', label: '商品表', fields: ['product_id', 'category_id', 'price', 'cost'] },
  { name: 'orders', label: '订单表', fields: ['order_id', 'customer_id', 'order_date', 'total_amount'] },
  { name: 'order_items', label: '订单明细', fields: ['order_id', 'product_id', 'quantity', 'unit_price'] },
  { name: 'payments', label: '支付表', fields: ['order_id', 'payment_method', 'payment_status'] },
  { name: 'refunds', label: '退款表', fields: ['order_id', 'refund_amount', 'refund_reason'] },
]

export function createMockResult(question) {
  // 后端 Agent 还没完全接通时，用同一份响应结构预览 UI，避免前端和 API 契约脱节。
  return {
    question,
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
    execution_time_ms: 42,
    retry_count: 0,
    optimization_suggestions: ['当前查询已按月份聚合，建议在真实 PostgreSQL 环境中关注 orders(order_date) 的过滤性能。'],
    used_mock: true,
  }
}

export async function queryAgent(question) {
  try {
    const response = await client.post('/chat/query', { question })
    // 后端返回 { code, message, data: { question, sql, rows, ... } }
    // 提取嵌套的 data 字段，与前端组件期望的结构对齐
    return { ...response.data.data, used_mock: false }
  } catch (error) {
    // mock fallback 只用于前端预览；真实联调时如果接口可用，会优先展示后端结果。
    return createMockResult(question)
  }
}

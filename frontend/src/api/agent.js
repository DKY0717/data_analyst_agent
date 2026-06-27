import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

export const exampleQuestions = [
  '统计 2024 年每个月的销售额',
  '找出销售额最高的前 10 个商品',
  '分析各商品类别的退款率',
  '统计不同地区的客户数量',
  '分析 2024 年用户复购率',
  '对比 2023 年和 2024 年的月度销售额',
  '按地区统计 2024 年销售额并排序',
  '计算每个月的客单价趋势',
  '找出退款金额最高的前 5 个商品类别',
  '分析各支付方式的使用占比',
  '统计最近 30 天的每日订单数',
  '按客户年龄段分析消费金额分布',
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

export async function queryAgent(question, sessionId, clarification = null) {
  const payload = { question, session_id: sessionId }
  if (clarification) {
    payload.clarification_id = clarification.clarificationId
    payload.clarification_candidate_id = clarification.candidateId
    payload.clarification_text = clarification.text || null
  }
  const response = await client.post('/chat/query', payload)
  return { ...response.data.data, used_mock: false }
}

export async function queryAgentSSE(question, sessionId, onProgress, signal) {
  const payload = { question, session_id: sessionId }

  const response = await fetch('/api/chat/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const jsonStr = line.slice(6)
      if (jsonStr === '[DONE]') continue

      try {
        const event = JSON.parse(jsonStr)

        if (event.type === 'progress') {
          onProgress(event.stage, event.progress, event.partial_result)
        } else if (event.type === 'result') {
          finalResult = { ...event.data, used_mock: false }
          onProgress('完成', 100, finalResult)
        } else if (event.type === 'error') {
          throw new Error(event.message)
        }
      } catch (parseError) {
        if (parseError.message && !parseError.message.includes('JSON')) {
          throw parseError
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error('SSE 流结束但未收到最终结果')
  }

  return finalResult
}

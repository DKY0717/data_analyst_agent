import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    // 普通 axios 请求统一带 JWT，保证前端标准查询和后端权限链路使用同一身份。
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
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

export const permissionDemoQuestions = [
  {
    role: 'analyst',
    question: '统计 2024 年每个月的销售额',
    expected: '允许：分析师可访问订单销售额指标',
  },
  {
    role: 'analyst',
    question: '列出客户姓名和注册日期',
    expected: '阻断：分析师不能访问 customers.customer_name',
  },
  {
    role: 'support',
    question: '查看支付金额最高的订单',
    expected: '阻断：客服不能访问 payments 或 paid_amount',
  },
  {
    role: 'admin',
    question: '列出客户姓名和注册日期',
    expected: '允许：管理员拥有全字段权限',
  },
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

function normalizeHttpError(status, fallback) {
  if (status === 401) return new Error('需要登录后才能查询')
  return new Error(fallback)
}

export async function demoLogin(role) {
  const response = await client.post('/auth/demo-login', { role })
  return response.data.data
}

export async function fetchCurrentUser() {
  const response = await client.get('/auth/me')
  return response.data
}

export async function fetchAuthStatus() {
  const response = await client.get('/auth/status')
  return response.data
}

export async function queryAgent(question, sessionId, clarification = null) {
  const payload = { question, session_id: sessionId }
  if (clarification) {
    payload.clarification_id = clarification.clarificationId
    payload.clarification_candidate_id = clarification.candidateId
    payload.clarification_text = clarification.text || null
  }
  try {
    const response = await client.post('/chat/query', payload)
    return { ...response.data.data, used_mock: false }
  } catch (error) {
    throw normalizeHttpError(error.response?.status, error.message || '查询请求失败')
  }
}

export async function queryAgentSSE(question, sessionId, onProgress, signal) {
  const payload = { question, session_id: sessionId }
  const auth = useAuthStore()

  const response = await fetch('/api/chat/query/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...auth.authHeaders,
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    throw normalizeHttpError(response.status, `HTTP ${response.status}: ${response.statusText}`)
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

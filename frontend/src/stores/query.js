import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { queryAgent } from '@/api/agent'

export const useQueryStore = defineStore('query', () => {
  const question = ref('统计 2024 年每个月的销售额')
  // 页面生命周期内复用同一个 session_id，让后端能够识别连续追问。
  const sessionId = ref(
    globalThis.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  )
  const loading = ref(false)
  const result = ref(null)
  const error = ref(null)
  const history = ref([])

  const hasResult = computed(() => Boolean(result.value))
  const hasRows = computed(() => Array.isArray(result.value?.rows) && result.value.rows.length > 0)

  async function submitQuestion(nextQuestion = question.value) {
    const normalizedQuestion = nextQuestion.trim()
    if (!normalizedQuestion || loading.value) return

    question.value = normalizedQuestion
    loading.value = true
    error.value = null

    try {
      const data = await queryAgent(normalizedQuestion, sessionId.value)
      result.value = data
      // 只保留最近 8 条，避免第一版内存历史过长影响侧栏可读性。
      history.value = [
        {
          question: normalizedQuestion,
          createdAt: new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          success: true,
        },
        ...history.value,
      ].slice(0, 8)
    } catch (requestError) {
      error.value = requestError
      result.value = null
      history.value = [
        {
          question: normalizedQuestion,
          createdAt: new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          success: false,
        },
        ...history.value,
      ].slice(0, 8)
    } finally {
      loading.value = false
    }
  }

  function setQuestion(nextQuestion) {
    question.value = nextQuestion
  }

  function clearResult() {
    result.value = null
    error.value = null
  }

  return {
    question,
    sessionId,
    loading,
    result,
    error,
    history,
    hasResult,
    hasRows,
    submitQuestion,
    setQuestion,
    clearResult,
  }
})

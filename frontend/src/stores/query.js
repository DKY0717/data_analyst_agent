import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { queryAgent, queryAgentSSE, fetchSchema } from '@/api/agent'

const FAVORITES_KEY = 'daa_favorites'

function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')
  } catch {
    return []
  }
}

export const useQueryStore = defineStore('query', () => {
  const question = ref('')
  const sessionId = ref(
    globalThis.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  )
  const loading = ref(false)
  const loadingStage = ref('')
  const loadingProgress = ref(0)
  const result = ref(null)
  const error = ref(null)
  const history = ref([])
  const schemaTables = ref([])
  const favorites = ref(loadFavorites())
  const useStreaming = ref(true)
  const abortController = ref(null)

  const hasResult = computed(() => Boolean(result.value))
  const hasRows = computed(() => Array.isArray(result.value?.rows) && result.value.rows.length > 0)
  const isFavorite = computed(() => (q) => favorites.value.some(f => f.question === q))

  function saveFavorites() {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites.value))
  }

  function toggleFavorite(item) {
    const idx = favorites.value.findIndex(f => f.question === item.question)
    if (idx >= 0) {
      favorites.value.splice(idx, 1)
    } else {
      favorites.value.unshift({
        question: item.question,
        createdAt: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        answer: item.answer || '',
      })
      if (favorites.value.length > 20) favorites.value.pop()
    }
    saveFavorites()
  }

  function removeFavorite(question) {
    favorites.value = favorites.value.filter(f => f.question !== question)
    saveFavorites()
  }

  function addToHistory(question, success, answer = '') {
    history.value = [
      {
        question,
        createdAt: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        success,
        answer,
      },
      ...history.value,
    ].slice(0, 20)
  }

  async function submitQuestion(nextQuestion = question.value, clarification = null) {
    const normalizedQuestion = nextQuestion.trim()
    if (!normalizedQuestion || loading.value) return

    question.value = normalizedQuestion
    loading.value = true
    loadingStage.value = '正在解析意图...'
    loadingProgress.value = 0
    error.value = null
    result.value = null

    try {
      let data
      if (useStreaming.value && !clarification) {
        abortController.value = new AbortController()
        data = await queryAgentSSE(
          normalizedQuestion,
          sessionId.value,
          (stage, progress, partial) => {
            loadingStage.value = stage
            loadingProgress.value = progress
            if (partial) {
              result.value = { ...result.value, ...partial }
            }
          },
          abortController.value.signal,
        )
        abortController.value = null
      } else {
        data = await queryAgent(normalizedQuestion, sessionId.value, clarification)
      }
      result.value = data
      addToHistory(normalizedQuestion, true, data?.answer)
    } catch (requestError) {
      if (requestError.name === 'AbortError') {
        loadingStage.value = '已取消'
      } else {
        error.value = requestError
        result.value = null
        addToHistory(normalizedQuestion, false)
      }
    } finally {
      abortController.value = null
      loading.value = false
      loadingStage.value = ''
      loadingProgress.value = 0
    }
  }

  function cancelQuery() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
  }

  function setQuestion(nextQuestion) {
    question.value = nextQuestion
  }

  async function submitClarification(option) {
    const clarification = result.value?.clarification
    if (!clarification || !option?.candidate_id) return

    await submitQuestion(option.label, {
      clarificationId: clarification.clarification_id,
      candidateId: option.candidate_id,
    })
  }

  function clearResult() {
    result.value = null
    error.value = null
  }

  async function loadSchema() {
    try {
      schemaTables.value = await fetchSchema()
    } catch {
      // Schema 加载失败不阻断主流程
    }
  }

  return {
    question,
    sessionId,
    loading,
    loadingStage,
    loadingProgress,
    result,
    error,
    history,
    schemaTables,
    favorites,
    useStreaming,
    hasResult,
    hasRows,
    isFavorite,
    submitQuestion,
    submitClarification,
    cancelQuery,
    setQuestion,
    clearResult,
    loadSchema,
    toggleFavorite,
    removeFavorite,
  }
})

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueryStore } from '@/stores/query'
import { exampleQuestions, permissionDemoQuestions } from '@/api/agent'
import QueryInput from '@/components/QueryInput.vue'
import ExampleQuestions from '@/components/ExampleQuestions.vue'
import AnswerPanel from '@/components/AnswerPanel.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import ResultTable from '@/components/ResultTable.vue'
import SQLPanel from '@/components/SQLPanel.vue'
import IntentPanel from '@/components/IntentPanel.vue'
import AuditPanel from '@/components/AuditPanel.vue'
import OptimizationPanel from '@/components/OptimizationPanel.vue'
import HistoryPanel from '@/components/HistoryPanel.vue'
import SchemaPanel from '@/components/SchemaPanel.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import AuthBar from '@/components/AuthBar.vue'

const store = useQueryStore()
const route = useRoute()
const router = useRouter()
const permissionQuestionLabels = computed(() => permissionDemoQuestions.map((item) => (
  `${item.role.toUpperCase()} - ${item.question} (${item.expected})`
)))
const executionMetrics = computed(() => {
  const result = store.result
  if (!result) return null

  // QueryResponse 顶层保存执行数据，审计报告只补充 LLM 调用汇总。
  return {
    row_count: Array.isArray(result.rows) ? result.rows.length : 0,
    total_latency_ms: result.execution_time_ms ?? 0,
    llm_call_count: result.audit_report?.llm_observability?.call_count ?? 0,
  }
})

function handleSelect(q) {
  store.question = q
  store.submitQuestion()
  router.replace({ name: 'query', params: { question: encodeURIComponent(q) } })
}

function handlePermissionSelect(label) {
  const item = permissionDemoQuestions.find((candidate) => label.includes(candidate.question))
  if (!item) return
  // 权限演示标签包含角色和预期说明，真正提交给 Agent 的仍然只是自然语言问题。
  handleSelect(item.question)
}

function handleSubmit() {
  if (!store.question.trim()) return
  router.replace({ name: 'query', params: { question: encodeURIComponent(store.question) } })
  store.submitQuestion()
}

function handleFavorite(item) {
  store.toggleFavorite(item)
}

function handleClarification(option) {
  // 保持候选对象原样传递，Store 负责拼装后端澄清契约。
  store.submitClarification(option)
}

onMounted(() => {
  store.loadSchema()
  if (route.params.question) {
    store.question = decodeURIComponent(route.params.question)
    store.submitQuestion()
  }
})

watch(() => store.result, (r) => {
  if (r?.answer) {
    document.title = `${store.question.slice(0, 30)} - Data Analyst Agent`
  }
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <div class="topbar-logo">⚡</div>
        <div>
          <span class="eyebrow">AI Data Workbench</span>
          <h1>Data Analyst Agent</h1>
        </div>
      </div>
      <div class="status-group">
        <AuthBar />
        <el-tag
          :type="store.schemaTables.length > 0 ? 'success' : 'warning'"
          effect="dark"
          round
          size="small"
        >
          <span class="status-dot" :class="store.schemaTables.length > 0 ? 'status-dot--ok' : 'status-dot--warn'" />
          DuckDB {{ store.schemaTables.length > 0 ? 'Connected' : 'Loading...' }}
        </el-tag>
        <el-tag effect="dark" round size="small" type="info">
          Session {{ store.sessionId.slice(0, 8) }}...
        </el-tag>
        <el-tag v-if="store.result?.used_mock" effect="dark" round size="small" type="warning">
          Mock Mode
        </el-tag>
        <el-switch
          v-model="store.useStreaming"
          active-text="SSE"
          inactive-text="标准"
          size="small"
          class="stream-switch"
        />
        <ThemeToggle />
      </div>
    </header>

    <main class="workbench-grid">
      <aside class="left-column">
        <QueryInput
          v-model="store.question"
          :loading="store.loading"
          :loading-stage="store.loadingStage"
          :loading-progress="store.loadingProgress"
          @submit="handleSubmit"
          @cancel="store.cancelQuery"
        />
        <ExampleQuestions
          :questions="exampleQuestions"
          @select="handleSelect"
        />
        <ExampleQuestions
          :questions="permissionQuestionLabels"
          @select="handlePermissionSelect"
        />
        <HistoryPanel
          :history="store.history"
          :favorites="store.favorites"
          :is-favorite="store.isFavorite"
          @select="handleSelect"
          @favorite="handleFavorite"
          @remove-favorite="store.removeFavorite"
        />
        <SchemaPanel :tables="store.schemaTables" />
      </aside>

      <section class="center-column">
        <AnswerPanel
          :loading="store.loading"
          :error="store.error"
          :answer="store.result?.answer"
          :execution-metrics="executionMetrics"
          :loading-stage="store.loadingStage"
        />
        <ChartPanel :data="store.result" />
        <ResultTable :data="store.result" />
      </section>

      <aside class="right-column">
        <IntentPanel
          :intent="store.result?.analysis_intent"
          :loading="store.loading"
          :clarification="store.result?.clarification"
          @clarify="handleClarification"
        />
        <SQLPanel
          :sql="store.result?.sql"
        />
        <AuditPanel :report="store.result?.audit_report" />
        <OptimizationPanel :result="store.result" />
      </aside>
    </main>
  </div>
</template>

<style scoped>
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
}

.status-dot--ok {
  background: var(--color-accent);
  box-shadow: 0 0 6px var(--color-accent);
}

.status-dot--warn {
  background: var(--color-warning);
  animation: pulse 1.2s infinite;
}

.stream-switch {
  --el-switch-on-color: var(--color-primary);
  --el-switch-off-color: var(--color-text-muted);
}
</style>

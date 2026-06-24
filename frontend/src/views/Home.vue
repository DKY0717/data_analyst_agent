<template>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <span class="eyebrow">AI Data Workbench</span>
        <h1>Data Analyst Agent</h1>
      </div>
      <div class="status-group">
        <el-tag type="success" effect="light">DuckDB 已连接</el-tag>
        <el-tag type="info" effect="light">会话 {{ queryStore.sessionId.slice(0, 8) }}</el-tag>
        <el-tag v-if="queryStore.result?.used_mock" type="warning" effect="light">Mock 兜底已启用</el-tag>
      </div>
    </header>

    <main class="workbench-grid">
      <aside class="left-column">
        <QueryInput
          v-model="queryStore.question"
          :loading="queryStore.loading"
          @submit="queryStore.submitQuestion"
        />
        <ExampleQuestions :questions="exampleQuestions" @select="handleSelectQuestion" />
        <HistoryPanel :history="queryStore.history" @select="handleSelectQuestion" />
        <SchemaPanel :tables="schemaTables" />
      </aside>

      <section class="center-column">
        <AnswerPanel
          :result="queryStore.result"
          :loading="queryStore.loading"
          :error="queryStore.error"
        />
        <ChartPanel :result="queryStore.result" />
        <ResultTable :result="queryStore.result" />
      </section>

      <aside class="right-column">
        <SQLPanel :result="queryStore.result" />
        <AuditPanel :result="queryStore.result" />
        <OptimizationPanel :result="queryStore.result" />
      </aside>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { exampleQuestions, schemaTables } from '@/api/agent'
import { useQueryStore } from '@/stores/query'
import AnswerPanel from '@/components/AnswerPanel.vue'
import AuditPanel from '@/components/AuditPanel.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import ExampleQuestions from '@/components/ExampleQuestions.vue'
import HistoryPanel from '@/components/HistoryPanel.vue'
import OptimizationPanel from '@/components/OptimizationPanel.vue'
import QueryInput from '@/components/QueryInput.vue'
import ResultTable from '@/components/ResultTable.vue'
import SchemaPanel from '@/components/SchemaPanel.vue'
import SQLPanel from '@/components/SQLPanel.vue'

const queryStore = useQueryStore()

function handleSelectQuestion(question) {
  queryStore.setQuestion(question)
}

onMounted(() => {
  // 首屏自动跑一次 mock/真实查询，让用户进入页面时直接看到完整展示效果。
  queryStore.submitQuestion(queryStore.question)
})
</script>

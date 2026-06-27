<template>
  <section class="panel answer-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">结果解释</h2>
        <p class="panel-subtitle">优先展示业务结论，再查看 SQL 和明细。</p>
      </div>
    </div>

    <div class="answer-content">
      <template v-if="loading">
        <div class="skeleton-group">
          <div class="skeleton skeleton-line" style="width: 100%"></div>
          <div class="skeleton skeleton-line" style="width: 85%"></div>
          <div class="skeleton skeleton-line" style="width: 65%"></div>
        </div>
        <p v-if="loadingStage" class="loading-stage">{{ loadingStage }}</p>
      </template>

      <template v-else-if="error">
        <div class="error-card">
          <span class="error-icon">✕</span>
          <div>
            <h4 class="error-title">分析失败</h4>
            <p class="error-desc">{{ error.message || '接口请求失败，请检查后端服务。' }}</p>
          </div>
        </div>
      </template>

      <template v-else-if="answer">
        <div class="answer-text markdown-body" v-html="renderedAnswer"></div>
        <div class="metric-row">
          <div class="metric-card">
            <span>返回行数</span>
            <strong>{{ executionMetrics?.row_count ?? 0 }}</strong>
          </div>
          <div class="metric-card">
            <span>执行耗时</span>
            <strong>{{ executionMetrics?.total_latency_ms ?? 0 }}ms</strong>
          </div>
          <div class="metric-card">
            <span>LLM调用</span>
            <strong>{{ executionMetrics?.llm_call_count ?? 0 }}</strong>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="empty-state">
          <h3>从一个业务问题开始</h3>
          <p>例如分析销售趋势、商品排行、地区表现或退款率。</p>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  answer: {
    type: String,
    default: '',
  },
  executionMetrics: {
    type: Object,
    default: null,
  },
  loadingStage: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: Object,
    default: null,
  },
})

const renderedAnswer = computed(() => {
  if (!props.answer) return ''
  try {
    return marked(props.answer, { breaks: true })
  } catch {
    return props.answer
  }
})
</script>

<style scoped>
.skeleton-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.skeleton-line {
  height: 14px;
  border-radius: var(--radius-sm);
}

.loading-stage {
  margin-top: var(--space-4);
  font-size: 13px;
  color: var(--color-text-muted);
  font-family: var(--font-body);
}

.error-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--color-bg-secondary);
  border-left: 3px solid var(--color-danger);
  border-radius: var(--radius-md);
}

.error-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

[data-theme="dark"] .error-icon {
  background: rgba(248, 113, 113, 0.15);
}

.error-title {
  margin: 0 0 var(--space-1);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  font-family: var(--font-display);
}

.error-desc {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-family: var(--font-body);
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 0.5em 0 0.25em;
  font-family: var(--font-display);
  color: var(--color-text);
}

.markdown-body :deep(h1) { font-size: 18px; }
.markdown-body :deep(h2) { font-size: 16px; }
.markdown-body :deep(h3) { font-size: 14px; }

.markdown-body :deep(p) {
  margin: 0 0 0.5em;
  line-height: 1.8;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 0.5em;
  padding-left: 1.5em;
}

.markdown-body :deep(li) {
  margin-bottom: 0.25em;
  line-height: 1.7;
}

.markdown-body :deep(code) {
  background: var(--color-code-bg);
  border-radius: 3px;
  padding: 1px 5px;
  font-family: var(--font-code);
  font-size: 13px;
  color: var(--color-primary);
}

.markdown-body :deep(pre) {
  background: var(--color-code-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  overflow-x: auto;
  margin: 0.5em 0;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: var(--color-text);
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--color-border);
  padding: 6px 10px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--color-bg-secondary);
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  margin: 0.5em 0;
  padding: 0.5em 1em;
  border-left: 3px solid var(--color-primary);
  background: var(--color-bg-secondary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--color-text-secondary);
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--color-text);
}
</style>

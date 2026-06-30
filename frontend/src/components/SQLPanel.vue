<template>
  <section class="panel detail-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">生成 SQL</h2>
        <p class="panel-subtitle">LLM 生成后经过 SQL Guard 校验。</p>
      </div>
      <div class="header-actions">
        <el-button
          v-if="sql"
          class="copy-btn"
          size="small"
          @click="copySql"
        >
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
        <el-tag :type="statusType" effect="dark" class="status-tag">
          {{ statusText }}
        </el-tag>
      </div>
    </div>

    <div class="sql-container">
      <pre class="sql-block"><code v-html="highlightedSql"></code></pre>
    </div>
  </section>
</template>

<script setup>
import { computed, inject } from 'vue'
import { CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'

const hljs = inject('hljs')

const props = defineProps({
  sql: {
    type: String,
    default: '',
  },
  changed: {
    type: Boolean,
    default: false,
  },
  optimizations: {
    type: Array,
    default: () => [],
  },
})

const statusType = computed(() => {
  if (!props.sql) return 'info'
  return props.changed ? 'warning' : 'success'
})

const statusText = computed(() => {
  if (!props.sql) return '等待生成'
  return props.changed ? '已优化' : 'SQL 安全通过'
})

const highlightedSql = computed(() => {
  if (!props.sql) return '提交问题后显示生成 SQL。'
  if (hljs) {
    return hljs.highlight(props.sql, { language: 'sql' }).value
  }
  return props.sql
})

const copySql = async () => {
  try {
    await navigator.clipboard.writeText(props.sql)
    ElMessage.success('SQL 已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.copy-btn {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-family: var(--font-body);
  transition: all var(--transition-hover);
}

.copy-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.status-tag {
  font-family: var(--font-body);
  font-size: 12px;
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-3);
}

.sql-container {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.sql-block {
  background: var(--color-code-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin: var(--space-4);
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
}

.sql-block code {
  font-family: var(--font-code), 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text);
  white-space: pre;
  tab-size: 2;
}

.sql-block::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.sql-block::-webkit-scrollbar-track {
  background: transparent;
}

.sql-block::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}

.sql-block::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}

:deep(.hljs-keyword) {
  color: #C792EA;
  font-weight: 500;
}

:deep(.hljs-string) {
  color: #C3E88D;
}

:deep(.hljs-number) {
  color: #F78C6C;
}

:deep(.hljs-function) {
  color: #82AAFF;
}

:deep(.hljs-title) {
  color: #82AAFF;
}

:deep(.hljs-params) {
  color: var(--color-text);
}

:deep(.hljs-comment) {
  color: var(--color-text-muted);
  font-style: italic;
}

:deep(.hljs-operator) {
  color: #89DDFF;
}

:deep(.hljs-punctuation) {
  color: var(--color-text-secondary);
}

:deep(.hljs-built_in) {
  color: #FFCB6B;
}
</style>

<template>
  <section class="panel detail-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">优化建议</h2>
        <p class="panel-subtitle">展示执行信息和可选优化建议。</p>
      </div>
    </div>

    <div class="execution-grid">
      <div>
        <span>执行耗时</span>
        <strong>{{ executionTime }}</strong>
      </div>
      <div>
        <span>重试次数</span>
        <strong>{{ report?.retry_count ?? '-' }}</strong>
      </div>
    </div>

    <ul v-if="suggestions.length" class="suggestion-list">
      <li v-for="item in suggestions" :key="item">{{ item }}</li>
    </ul>
    <div v-else class="empty-small">暂无优化建议。</div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  report: {
    type: Object,
    default: null,
  },
})

const suggestions = computed(() => props.report?.optimization_suggestions || [])
const executionTime = computed(() =>
  props.report?.execution_time_ms === undefined ? '-' : `${props.report.execution_time_ms}ms`,
)
</script>

<style scoped>
.execution-grid div {
  transition: all var(--transition-hover);
}

.execution-grid div:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.suggestion-list li {
  margin-bottom: var(--space-2);
  padding-left: var(--space-1);
}

.suggestion-list li:last-child {
  margin-bottom: 0;
}

.suggestion-list li::marker {
  color: var(--color-primary);
}
</style>

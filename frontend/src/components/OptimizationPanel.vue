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
        <span>retry</span>
        <strong>{{ result?.retry_count ?? '-' }}</strong>
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
  result: {
    type: Object,
    default: null,
  },
})

const suggestions = computed(() => props.result?.optimization_suggestions || [])
const executionTime = computed(() =>
  props.result?.execution_time_ms === undefined ? '-' : `${props.result.execution_time_ms}ms`,
)
</script>

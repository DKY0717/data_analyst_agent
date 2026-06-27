<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">🗄️ Schema 简览</h2>
        <p class="panel-subtitle">电商分析数据集，{{ tables.length }} 张核心表。</p>
      </div>
      <button class="toggle-btn" @click="expanded = !expanded">
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <div v-if="expanded" class="schema-list">
      <article v-for="table in tables" :key="table.name" class="schema-item">
        <div>
          <strong>{{ table.name }}</strong>
          <span>{{ table.label }}</span>
        </div>
        <p>{{ table.fields.join(' · ') }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  tables: {
    type: Array,
    required: true,
  },
})

const expanded = ref(true)
</script>

<style scoped>
.toggle-btn {
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 12px;
  padding: var(--space-1) var(--space-3);
  cursor: pointer;
  transition: all var(--transition-hover);
  font-family: var(--font-body);
}

.toggle-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: rgba(59, 130, 246, 0.05);
}

[data-theme="dark"] .toggle-btn:hover {
  background: rgba(96, 165, 250, 0.1);
}

.schema-list {
  max-height: 400px;
  overflow-y: auto;
}

.schema-item {
  transition: background var(--transition-hover);
  padding: var(--space-2) var(--space-1);
  margin: 0 calc(-1 * var(--space-1));
  border-radius: var(--radius-sm);
}

.schema-item:hover {
  background: var(--color-bg-secondary);
}
</style>

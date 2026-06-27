<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">💡 示例问题</h2>
        <p class="panel-subtitle">点击后可直接填入分析问题。</p>
      </div>
    </div>

    <div class="chip-list">
      <button
        v-for="(item, index) in questions"
        :key="item"
        class="question-chip"
        type="button"
        @click="handleSelect(item)"
      >
        <span class="chip-icon">{{ icons[index % icons.length] }}</span>
        {{ item }}
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  questions: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['select'])

const icons = ['📊', '📈', '💰', '👥', '🔄']

function handleSelect(question) {
  emit('select', question)
}
</script>

<style scoped>
.question-chip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  line-height: 1.5;
}

.question-chip:active {
  transform: scale(0.98);
  transition: transform var(--transition-active);
}

.chip-icon {
  flex-shrink: 0;
  font-size: 14px;
}
</style>

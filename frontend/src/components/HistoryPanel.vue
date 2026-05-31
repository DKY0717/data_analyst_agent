<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">查询历史</h2>
        <p class="panel-subtitle">本次会话最近的问题。</p>
      </div>
    </div>

    <div v-if="history.length" class="history-list">
      <button
        v-for="item in history"
        :key="`${item.createdAt}-${item.question}`"
        class="history-item"
        type="button"
        @click="$emit('select', item.question)"
      >
        <span>{{ item.question }}</span>
        <small>{{ item.createdAt }}</small>
      </button>
    </div>

    <div v-else class="empty-small">提交一次分析后会显示历史记录。</div>
  </section>
</template>

<script setup>
defineProps({
  history: {
    type: Array,
    required: true,
  },
})

defineEmits(['select'])
</script>

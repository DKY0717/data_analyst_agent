<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">示例问题</h2>
        <p class="panel-subtitle">点击后可直接填入分析问题。</p>
      </div>
    </div>

    <div class="chip-list">
      <button
        v-for="item in questions"
        :key="item"
        class="question-chip"
        type="button"
        @click="$emit('select', item)"
      >
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

defineEmits(['select'])
</script>

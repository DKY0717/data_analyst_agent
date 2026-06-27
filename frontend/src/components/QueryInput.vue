<template>
  <section class="panel query-card">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">自然语言问数</h2>
        <p class="panel-subtitle">输入业务问题，系统会生成安全 SQL 并返回分析结果。</p>
      </div>
    </div>

    <div class="query-body">
      <el-input
        v-model="localQuestion"
        type="textarea"
        :rows="5"
        resize="none"
        placeholder="例如：统计 2024 年每个月的销售额"
        @keydown.ctrl.enter.prevent="handleSubmit"
      />
      <div v-if="loading" class="progress-bar-wrap">
        <div class="progress-bar" :style="{ width: loadingProgress + '%' }"></div>
        <span class="progress-label">{{ loadingStage }}</span>
      </div>
      <div class="button-row">
        <el-button
          class="submit-button"
          type="primary"
          :loading="loading"
          :disabled="!localQuestion.trim()"
          @click="handleSubmit"
        >
          {{ loading ? '分析中...' : '开始分析' }}
        </el-button>
        <el-button
          v-if="loading"
          class="cancel-btn"
          @click="$emit('cancel')"
        >
          取消
        </el-button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  loadingStage: {
    type: String,
    default: '',
  },
  loadingProgress: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:modelValue', 'submit', 'cancel'])

const localQuestion = ref(props.modelValue)

watch(
  () => props.modelValue,
  (nextValue) => {
    localQuestion.value = nextValue
  },
)

watch(localQuestion, (nextValue) => {
  emit('update:modelValue', nextValue)
})

function handleSubmit() {
  if (!localQuestion.value.trim()) return
  emit('submit', localQuestion.value)
}
</script>

<style scoped>
.query-card :deep(.el-textarea__inner) {
  border-radius: var(--radius-md);
  border-color: var(--color-border);
  background: var(--color-bg-secondary);
  color: var(--color-text);
  font-family: var(--font-body);
  transition: all var(--transition-hover);
}

.query-card :deep(.el-textarea__inner:focus) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

[data-theme="dark"] .query-card :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.2);
}

.progress-bar-wrap {
  margin-top: var(--space-3);
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  overflow: hidden;
  position: relative;
  height: 28px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
  border-radius: var(--radius-full);
  transition: width 0.4s ease-out;
  min-width: 2%;
}

.progress-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-family: var(--font-body);
  color: var(--color-text);
  font-weight: 500;
  pointer-events: none;
}

.button-row {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.button-row .submit-button {
  flex: 1;
  margin-top: 0;
}

.cancel-btn {
  background: transparent;
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
  font-family: var(--font-body);
  transition: all var(--transition-hover);
}

.cancel-btn:hover {
  background: rgba(239, 68, 68, 0.1);
}
</style>

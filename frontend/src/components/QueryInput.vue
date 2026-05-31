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
      <el-button
        class="submit-button"
        type="primary"
        :loading="loading"
        :disabled="!localQuestion.trim()"
        @click="handleSubmit"
      >
        开始分析
      </el-button>
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
})

const emit = defineEmits(['update:modelValue', 'submit'])

const localQuestion = ref(props.modelValue)

watch(
  () => props.modelValue,
  (nextValue) => {
    // 支持示例问题和历史记录从外部回填输入框。
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

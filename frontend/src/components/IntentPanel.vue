<template>
  <section v-if="intent" class="panel detail-panel intent-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">意图解析</h2>
        <p class="panel-subtitle">结构化的分析意图信号。</p>
      </div>
      <el-tag :type="confidenceType" effect="light">
        {{ Math.round((intent.overall_confidence || 0) * 100) }}% 置信度
      </el-tag>
    </div>

    <div v-if="intent.metrics?.length" class="intent-section">
      <h4>指标</h4>
      <div class="intent-tags">
        <el-tag v-for="m in intent.metrics" :key="m.concept" type="primary" effect="plain">
          {{ m.evidence || m.concept }}
        </el-tag>
      </div>
    </div>

    <div v-if="intent.dimensions?.length" class="intent-section">
      <h4>维度</h4>
      <div class="intent-tags">
        <el-tag v-for="d in intent.dimensions" :key="d.concept" type="success" effect="plain">
          {{ d.evidence || d.concept }}
        </el-tag>
      </div>
    </div>

    <div v-if="intent.filters?.length" class="intent-section">
      <h4>过滤条件</h4>
      <div class="intent-tags">
        <el-tag v-for="f in intent.filters" :key="f.evidence" type="warning" effect="plain">
          {{ f.evidence }} {{ f.operator }} {{ f.value }}
        </el-tag>
      </div>
    </div>

    <div v-if="intent.ranking" class="intent-section">
      <h4>排序</h4>
      <el-tag type="info" effect="plain">
        {{ intent.ranking.direction === 'desc' ? '降序' : '升序' }} 前 {{ intent.ranking.limit }} 名
      </el-tag>
    </div>

    <div v-if="clarification" class="intent-section clarification">
      <h4>需要补充信息</h4>
      <p>{{ clarification.reason }}</p>
      <div v-if="clarification.options?.length" class="clarification-options">
        <el-tag
          v-for="opt in clarification.options"
          :key="opt.candidate_id"
          class="clickable-tag"
          effect="plain"
          @click="$emit('clarify', opt.label)"
        >
          {{ opt.label }}
        </el-tag>
      </div>
    </div>
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

defineEmits(['clarify'])

const intent = computed(() => props.result?.analysis_intent || null)

const clarification = computed(() => intent.value?.clarification || null)

const confidenceType = computed(() => {
  const c = intent.value?.overall_confidence || 0
  if (c >= 0.8) return 'success'
  if (c >= 0.5) return 'warning'
  return 'danger'
})
</script>

<style scoped>
.intent-section {
  margin-bottom: 12px;
}
.intent-section h4 {
  margin: 0 0 6px;
  font-size: 12px;
  color: #909399;
}
.intent-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.clarification {
  background: #fdf6ec;
  border-radius: 6px;
  padding: 10px;
}
.clarification-options {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.clickable-tag {
  cursor: pointer;
}
.clickable-tag:hover {
  opacity: 0.8;
}
</style>

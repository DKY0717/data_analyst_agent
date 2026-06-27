<template>
  <section class="panel detail-panel audit-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">安全审计</h2>
        <p class="panel-subtitle">展示 SQL 从生成到执行的安全证据。</p>
      </div>
      <el-tag :type="auditStatus.type" effect="light">{{ auditStatus.text }}</el-tag>
    </div>

    <template v-if="props.report">
      <div class="audit-summary">
        <div>
          <span>LIMIT 注入</span>
          <strong>{{ props.report.limit_injected ? '已注入' : '未触发' }}</strong>
        </div>
        <div>
          <span>阻断规则</span>
          <strong>{{ props.report.blocked_rules?.length || 0 }}</strong>
        </div>
      </div>

      <div v-if="props.report.blocked_rules?.length" class="audit-rules">
        <el-tag
          v-for="rule in props.report.blocked_rules"
          :key="rule"
          type="danger"
          effect="plain"
        >
          {{ rule }}
        </el-tag>
      </div>

      <div class="audit-events">
        <div v-for="(event, index) in props.report.events || []" :key="`${event.action}-${index}`" class="audit-event">
          <span class="audit-dot" :class="`audit-dot--${event.status}`"></span>
          <div>
            <div class="audit-event-title">
              <strong>{{ event.action }}</strong>
              <el-tag size="small" :type="eventTagType(event.status)" effect="plain">
                {{ event.status }}
              </el-tag>
            </div>
            <p>{{ event.message }}</p>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="empty-small">提交查询后显示安全审计事件。</div>
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

const auditStatus = computed(() => {
  if (!props.report) return { type: 'info', text: '等待审计' }
  if (!props.report.is_sql_safe) return { type: 'danger', text: '已拦截' }
  if (!props.report.execution_success) return { type: 'warning', text: '执行失败' }
  return { type: 'success', text: '审计通过' }
})

function eventTagType(status) {
  if (status === 'blocked' || status === 'failed') return 'danger'
  if (status === 'success') return 'success'
  return 'info'
}
</script>

<style scoped>
.audit-rules :deep(.el-tag) {
  border-radius: var(--radius-full);
  font-family: var(--font-body);
  font-size: 11px;
}

.audit-events {
  padding-bottom: var(--space-5);
}

.audit-event {
  position: relative;
}

.audit-event::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 16px;
  bottom: -8px;
  width: 2px;
  background: var(--color-border);
}

.audit-event:last-child::before {
  display: none;
}

.audit-event-title :deep(.el-tag) {
  font-family: var(--font-body);
  font-size: 11px;
  border-radius: var(--radius-sm);
}
</style>

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
      <div class="audit-summary audit-summary--identity">
        <div>
          <span>用户</span>
          <strong>{{ props.report.user_id || 'anonymous' }}</strong>
        </div>
        <div>
          <span>认证</span>
          <strong>{{ props.report.auth_method || 'none' }}</strong>
        </div>
        <div>
          <span>角色</span>
          <strong>{{ (props.report.roles || ['guest']).join(', ') }}</strong>
        </div>
      </div>

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

      <div class="permission-section">
        <div class="permission-section__header">
          <h3>数据权限</h3>
          <el-tag :type="permissionStatus.type" effect="plain">
            {{ permissionStatus.text }}
          </el-tag>
        </div>

        <div class="audit-summary permission-summary">
          <div>
            <span>权限检查</span>
            <strong>{{ permissionEvidence.permission_checked ? '已检查' : '未触发' }}</strong>
          </div>
          <div>
            <span>决策</span>
            <strong>{{ permissionDecisionText }}</strong>
          </div>
          <div>
            <span>SQL 改写</span>
            <strong>{{ permissionEvidence.authorized_sql_changed ? '已改写' : '未改写' }}</strong>
          </div>
        </div>

        <p v-if="!permissionEvidence.permission_checked" class="permission-empty">
          未触发权限检查
        </p>

        <template v-else>
          <div v-if="permissionEvidence.blocked_rule" class="permission-tags">
            <span class="permission-label">阻断规则</span>
            <el-tag type="danger" effect="plain">{{ permissionEvidence.blocked_rule }}</el-tag>
          </div>

          <div v-if="permissionEvidence.referenced_tables.length" class="permission-tags">
            <span class="permission-label">引用表</span>
            <el-tag
              v-for="table in permissionEvidence.referenced_tables"
              :key="table"
              effect="plain"
            >
              {{ table }}
            </el-tag>
          </div>

          <div v-if="permissionEvidence.referenced_columns.length" class="permission-tags">
            <span class="permission-label">引用字段</span>
            <el-tag
              v-for="column in permissionEvidence.referenced_columns"
              :key="column"
              effect="plain"
            >
              {{ column }}
            </el-tag>
          </div>

          <div v-if="permissionEvidence.row_filters_applied.length" class="permission-tags">
            <span class="permission-label">行级过滤</span>
            <el-tag
              v-for="filter in permissionEvidence.row_filters_applied"
              :key="`${filter.table}-${filter.rule_id}`"
              type="warning"
              effect="plain"
            >
              {{ filter.table }} / {{ filter.rule_id }}
            </el-tag>
          </div>
        </template>
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
        <div
          v-for="(event, index) in props.report.events || []"
          :key="`${event.action}-${index}`"
          class="audit-event"
          :class="{ 'audit-event--authorization': event.stage === 'authorization' }"
        >
          <span class="audit-dot" :class="`audit-dot--${event.status}`"></span>
          <div>
            <div class="audit-event-title">
              <strong>{{ event.action }}</strong>
              <span class="audit-event-stage">{{ event.stage }}</span>
              <span v-if="event.rule_id" class="audit-event-rule">{{ event.rule_id }}</span>
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

const permissionEvidence = computed(() => {
  const evidence = props.report?.permission_observability || {}
  return {
    permission_checked: Boolean(evidence.permission_checked),
    allowed: evidence.allowed ?? null,
    blocked_rule: evidence.blocked_rule || null,
    referenced_tables: Array.isArray(evidence.referenced_tables) ? evidence.referenced_tables : [],
    referenced_columns: Array.isArray(evidence.referenced_columns) ? evidence.referenced_columns : [],
    row_filters_applied: Array.isArray(evidence.row_filters_applied) ? evidence.row_filters_applied : [],
    authorized_sql_changed: Boolean(evidence.authorized_sql_changed),
  }
})

const permissionDecisionText = computed(() => {
  if (!permissionEvidence.value.permission_checked) return '未决策'
  if (permissionEvidence.value.allowed === true) return '允许'
  if (permissionEvidence.value.allowed === false) return '阻断'
  return '未决策'
})

const permissionStatus = computed(() => {
  if (!permissionEvidence.value.permission_checked) return { type: 'info', text: '未触发' }
  if (permissionEvidence.value.allowed === false) return { type: 'danger', text: '已阻断' }
  if (permissionEvidence.value.authorized_sql_changed) return { type: 'warning', text: '已改写' }
  return { type: 'success', text: '已允许' }
})

function eventTagType(status) {
  if (status === 'blocked' || status === 'failed') return 'danger'
  if (status === 'success') return 'success'
  return 'info'
}
</script>

<style scoped>
.audit-summary--identity {
  margin-bottom: var(--space-3);
}

.audit-rules :deep(.el-tag) {
  border-radius: var(--radius-full);
  font-family: var(--font-body);
  font-size: 11px;
}

.permission-section {
  margin: var(--space-4) var(--space-4) 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
}

.permission-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.permission-section__header h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 700;
}

.permission-summary {
  padding: 0;
  margin-bottom: var(--space-3);
}

.permission-empty {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.permission-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.permission-label {
  min-width: 52px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.permission-tags :deep(.el-tag),
.permission-section__header :deep(.el-tag) {
  border-radius: var(--radius-sm);
  font-family: var(--font-body);
  font-size: 11px;
}

.audit-events {
  padding-bottom: var(--space-5);
}

.audit-event {
  position: relative;
}

.audit-event--authorization {
  border-left: 3px solid var(--color-warning);
  padding-left: var(--space-3);
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

.audit-event-stage,
.audit-event-rule {
  color: var(--color-text-muted);
  font-size: 11px;
}
</style>

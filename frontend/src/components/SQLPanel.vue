<template>
  <section class="panel detail-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">生成 SQL</h2>
        <p class="panel-subtitle">LLM 生成后经过 SQL Guard 校验。</p>
      </div>
      <el-tag :type="result?.is_sql_safe ? 'success' : 'danger'" effect="light">
        {{ result?.is_sql_safe ? 'SQL 安全通过' : 'SQL 未通过' }}
      </el-tag>
    </div>

    <pre class="sql-block"><code>{{ result?.sql || '提交问题后显示生成 SQL。' }}</code></pre>
  </section>
</template>

<script setup>
defineProps({
  result: {
    type: Object,
    default: null,
  },
})
</script>

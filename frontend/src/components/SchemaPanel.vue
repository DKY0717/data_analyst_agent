<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">Schema 简览</h2>
        <p class="panel-subtitle">电商分析数据集，8 张核心表。</p>
      </div>
    </div>

    <div class="schema-list">
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
defineProps({
  tables: {
    type: Array,
    required: true,
  },
})
</script>

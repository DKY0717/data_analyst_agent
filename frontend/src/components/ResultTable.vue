<template>
  <section class="panel table-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">查询结果</h2>
        <p class="panel-subtitle">最多展示接口返回的结果行。</p>
      </div>
    </div>

    <el-table v-if="tableRows.length" :data="tableRows" height="280" stripe>
      <el-table-column
        v-for="column in columns"
        :key="column"
        :prop="column"
        :label="column"
        min-width="120"
      />
    </el-table>

    <div v-else class="empty-small">暂无结果数据。</div>
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

const columns = computed(() => props.result?.columns || [])
const tableRows = computed(() => {
  const rows = props.result?.rows || []
  // Element Plus 表格消费对象数组，这里把后端 columns + rows 转成稳定记录结构。
  return rows.map((row) =>
    columns.value.reduce((record, column, index) => {
      record[column] = row[index]
      return record
    }, {}),
  )
})
</script>

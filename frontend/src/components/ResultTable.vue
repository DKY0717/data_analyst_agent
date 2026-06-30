<template>
  <section class="panel table-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">查询结果</h2>
        <p class="panel-subtitle">共 {{ totalRows }} 行，{{ columns.length }} 列。</p>
      </div>
      <div class="header-actions">
        <el-button
          v-if="tableRows.length"
          class="export-btn"
          size="small"
          @click="exportCSV"
        >
          <el-icon><Download /></el-icon>
          CSV
        </el-button>
        <el-button
          v-if="tableRows.length"
          class="export-btn"
          size="small"
          @click="exportExcel"
        >
          <el-icon><Document /></el-icon>
          Excel
        </el-button>
      </div>
    </div>

    <el-table
      v-if="pagedRows.length"
      :data="pagedRows"
      :height="320"
      stripe
      border
      :default-sort="{ prop: columns[0], order: 'ascending' }"
    >
      <el-table-column
        v-for="column in columns"
        :key="column"
        :prop="column"
        :label="column"
        min-width="120"
        sortable
        show-overflow-tooltip
      />
    </el-table>

    <div v-else class="empty-small">暂无结果数据。</div>

    <div v-if="totalRows > pageSize" class="table-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalRows"
        layout="prev, pager, next, total"
        small
        background
      />
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Download, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'

const props = defineProps({
  data: {
    type: Object,
    default: null,
  },
})

const currentPage = ref(1)
const pageSize = 50

watch(() => props.data, () => {
  currentPage.value = 1
})

const columns = computed(() => props.data?.columns || [])
const totalRows = computed(() => props.data?.rows?.length || 0)

const tableRows = computed(() => {
  const rows = props.data?.rows || []
  return rows.map((row) =>
    columns.value.reduce((record, column, index) => {
      record[column] = row[index]
      return record
    }, {}),
  )
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return tableRows.value.slice(start, start + pageSize)
})

function exportCSV() {
  const cols = columns.value
  const rows = props.data?.rows || []
  const header = cols.join(',')
  const body = rows.map(r =>
    r.map(cell => {
      const str = String(cell ?? '')
      return str.includes(',') || str.includes('"') || str.includes('\n')
        ? `"${str.replace(/"/g, '""')}"`
        : str
    }).join(',')
  ).join('\n')
  const csv = '\uFEFF' + header + '\n' + body
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  downloadBlob(blob, `query_result_${Date.now()}.csv`)
  ElMessage.success('CSV 导出成功')
}

function exportExcel() {
  import('xlsx').then((XLSX) => {
    const cols = columns.value
    const rows = props.data?.rows || []
    const wsData = [cols, ...rows]
    const ws = XLSX.utils.aoa_to_sheet(wsData)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')
    const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
    const blob = new Blob([wbout], { type: 'application/octet-stream' })
    downloadBlob(blob, `query_result_${Date.now()}.xlsx`)
    ElMessage.success('Excel 导出成功')
  }).catch(() => {
    ElMessage.error('Excel 导出失败')
  })
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.export-btn {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-family: var(--font-body);
  transition: all var(--transition-hover);
}

.export-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.table-pagination {
  display: flex;
  justify-content: center;
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
}

.table-pagination :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--color-text-secondary);
  --el-pagination-button-bg-color: var(--color-bg-secondary);
  --el-pagination-hover-color: var(--color-primary);
}

.table-panel :deep(.el-table) {
  --el-table-bg-color: var(--color-panel);
  --el-table-tr-bg-color: var(--color-panel);
  --el-table-header-bg-color: var(--color-bg-secondary);
  --el-table-row-hover-bg-color: var(--color-bg-secondary);
  --el-table-border-color: var(--color-border);
  --el-table-text-color: var(--color-text);
  --el-table-header-text-color: var(--color-text-secondary);
  font-family: var(--font-body);
}

.table-panel :deep(.el-table__header th) {
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.table-panel :deep(.el-table__body td) {
  font-size: 13px;
}

.table-panel :deep(.el-table__body tr:hover > td) {
  background: var(--color-bg-secondary) !important;
}
</style>

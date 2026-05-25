<template>
  <section class="panel chart-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">图表展示</h2>
        <p class="panel-subtitle">根据返回字段自动选择基础图表。</p>
      </div>
    </div>
    <div v-if="chartOption" ref="chartRef" class="chart-canvas"></div>
    <div v-else class="empty-small">暂无可视化数据。</div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  result: {
    type: Object,
    default: null,
  },
})

const chartRef = ref(null)
let chartInstance = null

const chartOption = computed(() => {
  const columns = props.result?.columns || []
  const rows = props.result?.rows || []
  if (columns.length < 2 || rows.length === 0) return null

  const xValues = rows.map((row) => row[0])
  const yValues = rows.map((row) => Number(row[1]))
  const firstColumn = String(columns[0]).toLowerCase()
  // v0.3 只需要基础图表：时间维度用折线，类别维度用柱状，避免过早做复杂 BI 配置器。
  const chartType = firstColumn.includes('date') || firstColumn.includes('month') ? 'line' : 'bar'

  return {
    color: ['#1f9d8a'],
    tooltip: { trigger: 'axis' },
    grid: { top: 28, right: 20, bottom: 36, left: 52 },
    xAxis: { type: 'category', data: xValues, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series: [
      {
        name: columns[1],
        type: chartType,
        smooth: chartType === 'line',
        data: yValues,
        areaStyle: chartType === 'line' ? { opacity: 0.08 } : undefined,
        barMaxWidth: 38,
      },
    ],
  }
})

async function renderChart() {
  await nextTick()
  if (!chartRef.value || !chartOption.value) return
  chartInstance = chartInstance || echarts.init(chartRef.value)
  chartInstance.setOption(chartOption.value, true)
}

watch(chartOption, renderChart, { immediate: true })

onBeforeUnmount(() => {
  chartInstance?.dispose()
})
</script>

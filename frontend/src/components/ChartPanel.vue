<template>
  <section class="panel chart-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">图表展示</h2>
        <p class="panel-subtitle">根据数据特征自动推荐图表类型。</p>
      </div>
      <div v-if="chartOption" class="chart-type-group">
        <button
          v-for="t in availableTypes"
          :key="t.value"
          :class="['type-btn', { active: chartType === t.value }]"
          @click="chartType = t.value"
        >
          {{ t.label }}
        </button>
      </div>
    </div>
    <div v-if="chartOption" ref="chartRef" class="chart-canvas"></div>
    <div v-else class="empty-small">暂无可视化数据。</div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  data: {
    type: Object,
    default: null,
  },
})

const chartRef = ref(null)
let chartInstance = null
let echartsLoader = null
const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')
const chartType = ref('auto')

const availableTypes = [
  { label: '柱状图', value: 'bar' },
  { label: '折线图', value: 'line' },
  { label: '饼图', value: 'pie' },
  { label: '散点图', value: 'scatter' },
]

const COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#14B8A6', '#F97316', '#06B6D4', '#84CC16',
]

const COLORS_DARK = [
  '#60A5FA', '#34D399', '#FBBF24', '#F87171', '#A78BFA',
  '#F472B6', '#2DD4BF', '#FB923C', '#22D3EE', '#A3E635',
]

const columns = computed(() => props.data?.columns || [])
const rows = computed(() => props.data?.rows || [])

const detectedType = computed(() => {
  const cols = columns.value
  const rowCount = rows.value.length
  if (cols.length < 2 || rowCount === 0) return null

  const firstCol = String(cols[0]).toLowerCase()
  const numericCols = []
  for (let i = 1; i < cols.length; i++) {
    const vals = rows.value.map(r => Number(r[i])).filter(v => !isNaN(v))
    if (vals.length > rowCount * 0.5) numericCols.push(i)
  }

  if (numericCols.length === 0) return null

  if (firstCol.includes('date') || firstCol.includes('month') || firstCol.includes('time') || firstCol.includes('年') || firstCol.includes('月')) {
    return 'line'
  }

  if (rowCount <= 8 && cols.length === 2) {
    return 'pie'
  }

  return 'bar'
})

const effectiveType = computed(() => {
  if (chartType.value === 'auto') return detectedType.value
  return chartType.value
})

const chartOption = computed(() => {
  const cols = columns.value
  const dataRows = rows.value
  if (cols.length < 2 || dataRows.length === 0) return null

  const palette = isDark.value ? COLORS_DARK : COLORS
  const textColor = isDark.value ? '#94A3B8' : '#64748B'
  const borderColor = isDark.value ? '#334155' : '#E2E8F0'
  const bgColor = 'transparent'

  const numericCols = []
  for (let i = 1; i < cols.length; i++) {
    const vals = dataRows.map(r => Number(r[i])).filter(v => !isNaN(v))
    if (vals.length > dataRows.length * 0.5) numericCols.push(i)
  }
  if (numericCols.length === 0) return null

  const type = effectiveType.value
  if (!type) return null

  const xValues = dataRows.map(r => String(r[0]))

  const baseOption = {
    backgroundColor: bgColor,
    textStyle: { color: textColor, fontFamily: 'Inter, sans-serif' },
    color: palette,
    tooltip: {
      trigger: type === 'pie' ? 'item' : 'axis',
      backgroundColor: isDark.value ? '#1E293B' : '#FFFFFF',
      borderColor: isDark.value ? '#334155' : '#E2E8F0',
      textStyle: { color: isDark.value ? '#F1F5F9' : '#0F172A' },
    },
    legend: {
      show: numericCols.length > 1,
      top: 0,
      right: 0,
      textStyle: { color: textColor, fontSize: 11 },
    },
    grid: { top: numericCols.length > 1 ? 32 : 28, right: 20, bottom: 36, left: 52 },
  }

  if (type === 'pie') {
    const pieData = dataRows.map((r) => ({
      name: String(r[0]),
      value: Number(r[numericCols[0]]) || 0,
    }))

    return {
      ...baseOption,
      tooltip: {
        ...baseOption.tooltip,
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)',
      },
      legend: {
        ...baseOption.legend,
        show: true,
        orient: 'vertical',
        top: 'center',
        right: 10,
      },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        data: pieData,
        label: { show: dataRows.length <= 12, color: textColor, fontSize: 11 },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' },
        },
      }],
    }
  }

  if (type === 'scatter') {
    if (numericCols.length < 2) {
      const scatterData = dataRows.map((r, i) => [i, Number(r[numericCols[0]])])
      return {
        ...baseOption,
        xAxis: { type: 'value', axisLine: { lineStyle: { color: borderColor } }, splitLine: { lineStyle: { color: borderColor } }, axisLabel: { color: textColor } },
        yAxis: { type: 'value', axisLine: { lineStyle: { color: borderColor } }, splitLine: { lineStyle: { color: borderColor } }, axisLabel: { color: textColor } },
        series: [{ type: 'scatter', data: scatterData, symbolSize: 8, itemStyle: { color: palette[0] } }],
      }
    }
    const scatterData = dataRows.map(r => [Number(r[numericCols[0]]), Number(r[numericCols[1]])])
    return {
      ...baseOption,
      xAxis: { type: 'value', name: String(cols[numericCols[0]]), axisLine: { lineStyle: { color: borderColor } }, splitLine: { lineStyle: { color: borderColor } }, axisLabel: { color: textColor } },
      yAxis: { type: 'value', name: String(cols[numericCols[1]]), axisLine: { lineStyle: { color: borderColor } }, splitLine: { lineStyle: { color: borderColor } }, axisLabel: { color: textColor } },
      series: [{ type: 'scatter', data: scatterData, symbolSize: 8, itemStyle: { color: palette[0] } }],
    }
  }

  const series = numericCols.map((colIdx, i) => ({
    name: String(cols[colIdx]),
    type,
    smooth: type === 'line',
    data: dataRows.map(r => Number(r[colIdx]) || 0),
    itemStyle: { color: palette[i % palette.length] },
    lineStyle: { color: palette[i % palette.length], width: 2 },
    areaStyle: type === 'line' ? {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: palette[i % palette.length] + '4D' },
          { offset: 1, color: palette[i % palette.length] + '05' },
        ],
      },
    } : undefined,
    barMaxWidth: 38,
  }))

  return {
    ...baseOption,
    xAxis: {
      type: 'category',
      data: xValues,
      axisLine: { lineStyle: { color: borderColor } },
      axisTick: { show: false },
      axisLabel: { color: textColor },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: borderColor } },
      splitLine: { lineStyle: { color: borderColor } },
      axisLabel: { color: textColor },
    },
    series,
  }
})

function loadEcharts() {
  if (!echartsLoader) {
    echartsLoader = Promise.all([
      import('echarts/core'),
      import('echarts/charts'),
      import('echarts/components'),
      import('echarts/renderers'),
    ]).then(([
      { init, use },
      { BarChart, LineChart, PieChart, ScatterChart },
      { GridComponent, LegendComponent, TooltipComponent },
      { CanvasRenderer },
    ]) => {
      use([
        BarChart,
        LineChart,
        PieChart,
        ScatterChart,
        GridComponent,
        LegendComponent,
        TooltipComponent,
        CanvasRenderer,
      ])
      return { init }
    })
  }
  return echartsLoader
}

async function renderChart() {
  await nextTick()
  if (!chartRef.value || !chartOption.value) {
    if (chartInstance) {
      chartInstance.clear()
    }
    return
  }
  if (!chartInstance) {
    const echarts = await loadEcharts()
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(chartOption.value, true)
}

function handleResize() {
  chartInstance?.resize()
}

function handleThemeChange() {
  isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
}

watch(chartOption, renderChart, { immediate: true })
watch(chartType, renderChart)

onMounted(() => {
  window.addEventListener('resize', handleResize)
  const observer = new MutationObserver(handleThemeChange)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.chart-type-group {
  display: flex;
  gap: 2px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 2px;
}

.type-btn {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  font-family: var(--font-body);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 150ms ease-out;
  white-space: nowrap;
}

.type-btn:hover {
  color: var(--color-text);
}

.type-btn.active {
  background: var(--color-primary);
  color: white;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.3);
}

[data-theme="dark"] .type-btn.active {
  background: var(--color-primary);
  box-shadow: 0 1px 3px rgba(96, 165, 250, 0.3);
}
</style>

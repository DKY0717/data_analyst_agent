# Frontend Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Vue frontend for Data Analyst Agent as a modern AI data analysis workbench that can submit natural-language questions, display mock or real query results, and expose SQL safety/execution details.

**Architecture:** Create a Vue 3 + Vite single-page frontend under `frontend/`. Use Pinia for query state, Axios for backend calls with mock fallback, Element Plus for controls/tables, and ECharts for result visualization. Keep the UI split into focused components: input/context sidebar, central analysis results, and right-side SQL/optimization details.

**Tech Stack:** Vue 3, Vite 5, Element Plus, Pinia, Axios, ECharts, JavaScript, CSS.

---

## File Structure

Create or modify these frontend files:

```text
frontend/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── api/
│   │   └── agent.js
│   ├── components/
│   │   ├── AnswerPanel.vue
│   │   ├── ChartPanel.vue
│   │   ├── ExampleQuestions.vue
│   │   ├── HistoryPanel.vue
│   │   ├── OptimizationPanel.vue
│   │   ├── QueryInput.vue
│   │   ├── ResultTable.vue
│   │   ├── SQLPanel.vue
│   │   └── SchemaPanel.vue
│   ├── stores/
│   │   └── query.js
│   ├── styles/
│   │   └── main.css
│   └── views/
│       └── Home.vue
```

File responsibilities:

- `package.json`: frontend dependencies and scripts.
- `vite.config.js`: Vite setup and `/api` proxy to `localhost:8000`.
- `src/main.js`: Vue app bootstrap, Pinia, Element Plus, global CSS.
- `src/api/agent.js`: query API wrapper, mock result fallback, schema mock.
- `src/stores/query.js`: current question, result, loading, error, history, submit flow.
- `src/views/Home.vue`: three-column workbench layout.
- `src/components/*.vue`: focused presentational and interaction components.
- `src/styles/main.css`: design tokens, layout, responsive behavior.

## Task 1: Scaffold Vue Frontend Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/styles/main.css`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "data-analyst-agent-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.6.8",
    "echarts": "^5.5.0",
    "element-plus": "^2.7.2",
    "pinia": "^2.1.7",
    "vue": "^3.4.21"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.4",
    "vite": "^5.2.0"
  }
}
```

- [ ] **Step 2: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Analyst Agent</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 3: Create `frontend/vite.config.js`**

```javascript
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: Create `frontend/src/main.js`**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/main.css'
import App from './App.vue'

const app = createApp(App)

app.use(createPinia())
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 5: Create `frontend/src/App.vue`**

```vue
<template>
  <Home />
</template>

<script setup>
import Home from '@/views/Home.vue'
</script>
```

- [ ] **Step 6: Create initial `frontend/src/styles/main.css`**

```css
:root {
  color: #172033;
  background: #f5f7fb;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    "Microsoft YaHei", sans-serif;
  --color-bg: #f5f7fb;
  --color-panel: #ffffff;
  --color-border: #dfe5ef;
  --color-muted: #667085;
  --color-primary: #1f9d8a;
  --color-primary-dark: #147766;
  --color-blue: #3478f6;
  --color-safe: #17a66a;
  --color-warning: #b7791f;
  --color-danger: #d92d20;
  --shadow-panel: 0 12px 30px rgba(15, 23, 42, 0.06);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: var(--color-bg);
}

button,
input,
textarea {
  font: inherit;
}

.panel {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  box-shadow: var(--shadow-panel);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 0;
}

.panel-title {
  margin: 0;
  color: #101828;
  font-size: 15px;
  font-weight: 700;
}

.panel-subtitle {
  margin: 4px 0 0;
  color: var(--color-muted);
  font-size: 12px;
}
```

- [ ] **Step 7: Install dependencies**

Run:

```bash
cd frontend
npm install
```

Expected: `node_modules/` and `package-lock.json` are created without dependency resolution errors.

- [ ] **Step 8: Verify scaffold build**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite build succeeds and writes `frontend/dist/`.

- [ ] **Step 9: Commit scaffold**

```bash
git add frontend/package.json frontend/package-lock.json frontend/index.html frontend/vite.config.js frontend/src/main.js frontend/src/App.vue frontend/src/styles/main.css
git commit -m "feat: scaffold Vue frontend"
```

## Task 2: Add API Client and Query Store

**Files:**
- Create: `frontend/src/api/agent.js`
- Create: `frontend/src/stores/query.js`

- [ ] **Step 1: Create `frontend/src/api/agent.js`**

```javascript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const exampleQuestions = [
  '统计 2024 年每个月的销售额',
  '找出销售额最高的 10 个商品',
  '分析各商品类别的退款率',
  '统计不同地区的客户数量',
  '分析 2024 年用户复购率',
]

export const schemaTables = [
  { name: 'regions', label: '地区表', fields: ['region_id', 'region_name', 'province', 'city'] },
  { name: 'customers', label: '用户表', fields: ['customer_id', 'gender', 'age', 'region_id'] },
  { name: 'categories', label: '类别表', fields: ['category_id', 'category_name'] },
  { name: 'products', label: '商品表', fields: ['product_id', 'category_id', 'price', 'cost'] },
  { name: 'orders', label: '订单表', fields: ['order_id', 'customer_id', 'order_date', 'total_amount'] },
  { name: 'order_items', label: '订单明细', fields: ['order_id', 'product_id', 'quantity', 'unit_price'] },
  { name: 'payments', label: '支付表', fields: ['order_id', 'payment_method', 'payment_status'] },
  { name: 'refunds', label: '退款表', fields: ['order_id', 'refund_amount', 'refund_reason'] },
]

export function createMockResult(question) {
  return {
    question,
    sql: `SELECT
  strftime(order_date, '%Y-%m') AS month,
  SUM(total_amount) AS sales
FROM orders
WHERE order_date >= DATE '2024-01-01'
  AND order_date < DATE '2025-01-01'
GROUP BY month
ORDER BY month
LIMIT 1000;`,
    is_sql_safe: true,
    columns: ['month', 'sales'],
    rows: [
      ['2024-01', 12840.5],
      ['2024-02', 14520.8],
      ['2024-03', 16890.3],
      ['2024-04', 15330.2],
      ['2024-05', 18110.7],
      ['2024-06', 19780.4],
    ],
    answer: '查询结果显示，2024 年上半年销售额整体呈上升趋势，其中 6 月销售额最高，达到 19780.4 元。',
    execution_time_ms: 42,
    retry_count: 0,
    optimization_suggestions: ['当前查询已按月份聚合，建议在真实 PostgreSQL 环境中关注 orders(order_date) 的过滤性能。'],
    used_mock: true,
  }
}

export async function queryAgent(question) {
  try {
    const response = await client.post('/chat/query', { question })
    return { ...response.data, used_mock: false }
  } catch (error) {
    return createMockResult(question)
  }
}
```

- [ ] **Step 2: Create `frontend/src/stores/query.js`**

```javascript
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { queryAgent } from '@/api/agent'

export const useQueryStore = defineStore('query', () => {
  const question = ref('统计 2024 年每个月的销售额')
  const loading = ref(false)
  const result = ref(null)
  const error = ref(null)
  const history = ref([])

  const hasResult = computed(() => Boolean(result.value))
  const hasRows = computed(() => Array.isArray(result.value?.rows) && result.value.rows.length > 0)

  async function submitQuestion(nextQuestion = question.value) {
    const normalizedQuestion = nextQuestion.trim()
    if (!normalizedQuestion || loading.value) return

    question.value = normalizedQuestion
    loading.value = true
    error.value = null

    try {
      const data = await queryAgent(normalizedQuestion)
      result.value = data
      history.value = [
        {
          question: normalizedQuestion,
          createdAt: new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          success: true,
        },
        ...history.value,
      ].slice(0, 8)
    } catch (requestError) {
      error.value = requestError
      result.value = null
      history.value = [
        {
          question: normalizedQuestion,
          createdAt: new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          success: false,
        },
        ...history.value,
      ].slice(0, 8)
    } finally {
      loading.value = false
    }
  }

  function setQuestion(nextQuestion) {
    question.value = nextQuestion
  }

  return {
    question,
    loading,
    result,
    error,
    history,
    hasResult,
    hasRows,
    submitQuestion,
    setQuestion,
  }
})
```

- [ ] **Step 3: Verify API/store syntax**

Run:

```bash
cd frontend
npm run build
```

Expected: Build succeeds with no import or syntax errors.

- [ ] **Step 4: Commit API/store**

```bash
git add frontend/src/api/agent.js frontend/src/stores/query.js
git commit -m "feat: add frontend query state"
```

## Task 3: Build Sidebar Components

**Files:**
- Create: `frontend/src/components/QueryInput.vue`
- Create: `frontend/src/components/ExampleQuestions.vue`
- Create: `frontend/src/components/HistoryPanel.vue`
- Create: `frontend/src/components/SchemaPanel.vue`

- [ ] **Step 1: Create `frontend/src/components/QueryInput.vue`**

```vue
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
```

- [ ] **Step 2: Create `frontend/src/components/ExampleQuestions.vue`**

```vue
<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">示例问题</h2>
        <p class="panel-subtitle">点击后可直接填入分析问题。</p>
      </div>
    </div>

    <div class="chip-list">
      <button
        v-for="item in questions"
        :key="item"
        class="question-chip"
        type="button"
        @click="$emit('select', item)"
      >
        {{ item }}
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  questions: {
    type: Array,
    required: true,
  },
})

defineEmits(['select'])
</script>
```

- [ ] **Step 3: Create `frontend/src/components/HistoryPanel.vue`**

```vue
<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">查询历史</h2>
        <p class="panel-subtitle">本次会话最近的问题。</p>
      </div>
    </div>

    <div v-if="history.length" class="history-list">
      <button
        v-for="item in history"
        :key="`${item.createdAt}-${item.question}`"
        class="history-item"
        type="button"
        @click="$emit('select', item.question)"
      >
        <span>{{ item.question }}</span>
        <small>{{ item.createdAt }}</small>
      </button>
    </div>

    <div v-else class="empty-small">提交一次分析后会显示历史记录。</div>
  </section>
</template>

<script setup>
defineProps({
  history: {
    type: Array,
    required: true,
  },
})

defineEmits(['select'])
</script>
```

- [ ] **Step 4: Create `frontend/src/components/SchemaPanel.vue`**

```vue
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
```

- [ ] **Step 5: Verify sidebar components compile**

Run:

```bash
cd frontend
npm run build
```

Expected: Build succeeds. Components may be unused until Task 5, but imports should be valid when added later.

- [ ] **Step 6: Commit sidebar components**

```bash
git add frontend/src/components/QueryInput.vue frontend/src/components/ExampleQuestions.vue frontend/src/components/HistoryPanel.vue frontend/src/components/SchemaPanel.vue
git commit -m "feat: add workbench sidebar components"
```

## Task 4: Build Result and Detail Components

**Files:**
- Create: `frontend/src/components/AnswerPanel.vue`
- Create: `frontend/src/components/ChartPanel.vue`
- Create: `frontend/src/components/ResultTable.vue`
- Create: `frontend/src/components/SQLPanel.vue`
- Create: `frontend/src/components/OptimizationPanel.vue`

- [ ] **Step 1: Create `frontend/src/components/AnswerPanel.vue`**

```vue
<template>
  <section class="panel answer-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">结果解释</h2>
        <p class="panel-subtitle">优先展示业务结论，再查看 SQL 和明细。</p>
      </div>
      <el-tag v-if="result?.used_mock" type="warning" effect="light">Mock 数据</el-tag>
    </div>

    <div class="answer-content">
      <template v-if="loading">
        <el-steps :active="2" finish-status="success" simple>
          <el-step title="读取 Schema" />
          <el-step title="生成 SQL" />
          <el-step title="安全校验" />
          <el-step title="执行查询" />
        </el-steps>
      </template>

      <template v-else-if="error">
        <el-alert
          title="分析失败"
          type="error"
          :description="error.message || '接口请求失败，请检查后端服务。'"
          show-icon
          :closable="false"
        />
      </template>

      <template v-else-if="result">
        <p class="answer-text">{{ result.answer }}</p>
        <div class="metric-row">
          <div class="metric-card">
            <span>返回行数</span>
            <strong>{{ result.rows?.length || 0 }}</strong>
          </div>
          <div class="metric-card">
            <span>执行耗时</span>
            <strong>{{ result.execution_time_ms }}ms</strong>
          </div>
          <div class="metric-card">
            <span>修复次数</span>
            <strong>{{ result.retry_count }}</strong>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="empty-state">
          <h3>从一个业务问题开始</h3>
          <p>例如分析销售趋势、商品排行、地区表现或退款率。</p>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
defineProps({
  result: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: Object,
    default: null,
  },
})
</script>
```

- [ ] **Step 2: Create `frontend/src/components/ChartPanel.vue`**

```vue
<template>
  <section class="panel chart-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">图表展示</h2>
        <p class="panel-subtitle">根据返回字段自动选择基础图表。</p>
      </div>
    </div>
    <div ref="chartRef" class="chart-canvas"></div>
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
```

- [ ] **Step 3: Create `frontend/src/components/ResultTable.vue`**

```vue
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
  return rows.map((row) =>
    columns.value.reduce((record, column, index) => {
      record[column] = row[index]
      return record
    }, {}),
  )
})
</script>
```

- [ ] **Step 4: Create `frontend/src/components/SQLPanel.vue`**

```vue
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
```

- [ ] **Step 5: Create `frontend/src/components/OptimizationPanel.vue`**

```vue
<template>
  <section class="panel detail-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">优化建议</h2>
        <p class="panel-subtitle">展示执行信息和可选优化建议。</p>
      </div>
    </div>

    <div class="execution-grid">
      <div>
        <span>执行耗时</span>
        <strong>{{ result?.execution_time_ms ?? '-' }}ms</strong>
      </div>
      <div>
        <span>retry</span>
        <strong>{{ result?.retry_count ?? '-' }}</strong>
      </div>
    </div>

    <ul v-if="suggestions.length" class="suggestion-list">
      <li v-for="item in suggestions" :key="item">{{ item }}</li>
    </ul>
    <div v-else class="empty-small">暂无优化建议。</div>
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

const suggestions = computed(() => props.result?.optimization_suggestions || [])
</script>
```

- [ ] **Step 6: Verify result/detail components compile**

Run:

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit result/detail components**

```bash
git add frontend/src/components/AnswerPanel.vue frontend/src/components/ChartPanel.vue frontend/src/components/ResultTable.vue frontend/src/components/SQLPanel.vue frontend/src/components/OptimizationPanel.vue
git commit -m "feat: add analysis result components"
```

## Task 5: Compose the Workbench Page

**Files:**
- Create: `frontend/src/views/Home.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Create `frontend/src/views/Home.vue`**

```vue
<template>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <span class="eyebrow">AI Data Workbench</span>
        <h1>Data Analyst Agent</h1>
      </div>
      <div class="status-group">
        <el-tag type="success" effect="light">DuckDB 已连接</el-tag>
        <el-tag type="success" effect="light">Backend Ready</el-tag>
      </div>
    </header>

    <main class="workbench-grid">
      <aside class="left-column">
        <QueryInput
          v-model="queryStore.question"
          :loading="queryStore.loading"
          @submit="queryStore.submitQuestion"
        />
        <ExampleQuestions :questions="exampleQuestions" @select="handleSelectQuestion" />
        <HistoryPanel :history="queryStore.history" @select="handleSelectQuestion" />
        <SchemaPanel :tables="schemaTables" />
      </aside>

      <section class="center-column">
        <AnswerPanel
          :result="queryStore.result"
          :loading="queryStore.loading"
          :error="queryStore.error"
        />
        <ChartPanel :result="queryStore.result" />
        <ResultTable :result="queryStore.result" />
      </section>

      <aside class="right-column">
        <SQLPanel :result="queryStore.result" />
        <OptimizationPanel :result="queryStore.result" />
      </aside>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { exampleQuestions, schemaTables } from '@/api/agent'
import { useQueryStore } from '@/stores/query'
import AnswerPanel from '@/components/AnswerPanel.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import ExampleQuestions from '@/components/ExampleQuestions.vue'
import HistoryPanel from '@/components/HistoryPanel.vue'
import OptimizationPanel from '@/components/OptimizationPanel.vue'
import QueryInput from '@/components/QueryInput.vue'
import ResultTable from '@/components/ResultTable.vue'
import SchemaPanel from '@/components/SchemaPanel.vue'
import SQLPanel from '@/components/SQLPanel.vue'

const queryStore = useQueryStore()

function handleSelectQuestion(question) {
  queryStore.setQuestion(question)
}

onMounted(() => {
  queryStore.submitQuestion(queryStore.question)
})
</script>
```

- [ ] **Step 2: Replace `frontend/src/styles/main.css` with complete layout styles**

```css
:root {
  color: #172033;
  background: #f5f7fb;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    "Microsoft YaHei", sans-serif;
  --color-bg: #f5f7fb;
  --color-panel: #ffffff;
  --color-border: #dfe5ef;
  --color-muted: #667085;
  --color-primary: #1f9d8a;
  --color-primary-dark: #147766;
  --color-blue: #3478f6;
  --color-safe: #17a66a;
  --color-warning: #b7791f;
  --color-danger: #d92d20;
  --shadow-panel: 0 12px 30px rgba(15, 23, 42, 0.06);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: var(--color-bg);
}

button,
input,
textarea {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  padding: 24px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 auto 18px;
  max-width: 1480px;
}

.topbar h1 {
  margin: 2px 0 0;
  color: #101828;
  font-size: 24px;
  line-height: 1.2;
}

.eyebrow {
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.status-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.workbench-grid {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(520px, 1fr) minmax(280px, 360px);
  gap: 16px;
  align-items: start;
  max-width: 1480px;
  margin: 0 auto;
}

.left-column,
.center-column,
.right-column {
  display: grid;
  gap: 16px;
}

.panel {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  box-shadow: var(--shadow-panel);
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 0;
}

.panel-title {
  margin: 0;
  color: #101828;
  font-size: 15px;
  font-weight: 700;
}

.panel-subtitle {
  margin: 4px 0 0;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}

.query-body,
.answer-content {
  padding: 16px 18px 18px;
}

.submit-button {
  width: 100%;
  margin-top: 12px;
}

.compact-panel {
  overflow: hidden;
}

.chip-list,
.history-list,
.schema-list {
  display: grid;
  gap: 8px;
  padding: 14px 18px 18px;
}

.question-chip,
.history-item {
  width: 100%;
  border: 1px solid #e4e9f2;
  border-radius: 8px;
  background: #f9fbff;
  color: #26364f;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}

.question-chip {
  padding: 9px 10px;
  font-size: 13px;
}

.question-chip:hover,
.history-item:hover {
  border-color: rgba(31, 157, 138, 0.5);
  background: #f0fbf8;
}

.history-item {
  display: grid;
  gap: 4px;
  padding: 10px;
}

.history-item span {
  color: #26364f;
  font-size: 13px;
}

.history-item small {
  color: var(--color-muted);
  font-size: 11px;
}

.schema-item {
  border-bottom: 1px solid #edf1f7;
  padding-bottom: 8px;
}

.schema-item:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.schema-item div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.schema-item strong {
  color: #172033;
  font-size: 13px;
}

.schema-item span,
.schema-item p {
  color: var(--color-muted);
  font-size: 12px;
}

.schema-item p {
  margin: 5px 0 0;
  line-height: 1.5;
}

.answer-text {
  margin: 0;
  color: #172033;
  font-size: 15px;
  line-height: 1.8;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 16px;
}

.metric-card {
  border: 1px solid #e7edf5;
  border-radius: 8px;
  padding: 12px;
  background: #fbfcff;
}

.metric-card span,
.execution-grid span {
  display: block;
  color: var(--color-muted);
  font-size: 12px;
}

.metric-card strong,
.execution-grid strong {
  display: block;
  margin-top: 6px;
  color: #101828;
  font-size: 18px;
}

.chart-canvas {
  width: 100%;
  height: 320px;
  padding: 8px;
}

.table-panel {
  overflow: hidden;
}

.empty-state,
.empty-small {
  color: var(--color-muted);
  text-align: center;
}

.empty-state {
  padding: 48px 20px;
}

.empty-state h3 {
  margin: 0 0 8px;
  color: #172033;
}

.empty-small {
  padding: 18px;
  font-size: 13px;
}

.sql-block {
  margin: 16px 18px 18px;
  max-height: 360px;
  overflow: auto;
  border: 1px solid #e4e9f2;
  border-radius: 8px;
  background: #f8fafc;
  color: #23344e;
  padding: 14px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.execution-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 16px 18px 0;
}

.execution-grid div {
  border: 1px solid #e7edf5;
  border-radius: 8px;
  padding: 12px;
  background: #fbfcff;
}

.suggestion-list {
  margin: 12px 18px 18px;
  padding-left: 18px;
  color: #344054;
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1180px) {
  .workbench-grid {
    grid-template-columns: 300px minmax(0, 1fr);
  }

  .right-column {
    grid-column: 1 / -1;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .app-shell {
    padding: 16px;
  }

  .topbar,
  .workbench-grid {
    display: grid;
    grid-template-columns: 1fr;
  }

  .right-column {
    grid-template-columns: 1fr;
  }

  .metric-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Verify composed page build**

Run:

```bash
cd frontend
npm run build
```

Expected: Build succeeds and includes all components.

- [ ] **Step 4: Commit workbench composition**

```bash
git add frontend/src/views/Home.vue frontend/src/styles/main.css
git commit -m "feat: compose frontend workbench"
```

## Task 6: Run and Visually Verify the Frontend

**Files:**
- Modify only if visual QA reveals a concrete issue: `frontend/src/styles/main.css` or the affected component file.

- [ ] **Step 1: Start the frontend dev server**

Run:

```bash
cd frontend
npm run dev
```

Expected: Vite starts at `http://localhost:3000`.

- [ ] **Step 2: Open the app in the browser**

Open:

```text
http://localhost:3000
```

Expected: The page shows a light three-column Data Analyst Agent workbench with question input, result area, chart/table area, and SQL detail panel.

- [ ] **Step 3: Test the default mock query**

Action: Wait for initial mounted query to complete, or click `开始分析`.

Expected:

- The answer panel shows a Chinese explanation.
- The chart panel renders a line chart.
- The table shows `month` and `sales` columns.
- The SQL panel shows `SQL 安全通过`.
- Optimization panel shows `执行耗时 42ms` and `retry 0`.

- [ ] **Step 4: Test example question selection**

Action: Click `找出销售额最高的 10 个商品`, then click `开始分析`.

Expected:

- The input updates to the selected question.
- The history list records the submitted question.
- Mock fallback still returns a usable result if the backend endpoint is not implemented.

- [ ] **Step 5: Test responsive layout**

Action: Resize the browser below 820px width.

Expected:

- Columns stack vertically.
- Text stays inside panels.
- Buttons remain full-width and usable.
- SQL block scrolls instead of expanding off screen.

- [ ] **Step 6: Run production build after visual fixes**

Run:

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit visual QA fixes**

If no files changed after QA, skip this commit. If styles or components changed:

```bash
git add frontend/src
git commit -m "fix: polish frontend workbench layout"
```

## Task 7: Update Diary and Final Verification

**Files:**
- Modify: `logs/work-diary.md`

- [ ] **Step 1: Update `logs/work-diary.md`**

Add a concise Chinese entry:

```markdown
## 2026-05-25 — 第五次会话

### 完成的工作

**前端工作台实现** ✅
- 搭建 Vue 3 + Vite + Element Plus + Pinia + ECharts 前端工程。
- 实现现代 AI 数据分析工作台首页。
- 支持自然语言输入、示例问题、查询历史、Schema 简览、回答解释、图表、结果表格、SQL 安全状态和优化建议。
- 支持 `/api/chat/query` 调用和 mock 数据兜底。

### 遗留问题

- 查询历史第一版仅保存在前端内存中。
- 后端 Agent 完整接口实现后，需要用真实响应再做一次联调。

### 当前进度

- ✅ 前端第一版工作台已完成
- ⏳ 后端 Agent/API 联调待完成

### 下一步

- 完成后端 LLM Service、SQL Generator、Agent Graph 和 `/api/chat/query`。
- 使用真实后端接口验证前端展示。
```

- [ ] **Step 2: Run final build**

Run:

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Check Git status**

Run:

```bash
git status --short
```

Expected: Only intended frontend files and `logs/work-diary.md` are modified or staged.

- [ ] **Step 4: Commit diary update**

```bash
git add logs/work-diary.md
git commit -m "docs: update work diary for frontend workbench"
```

## Self-Review

Spec coverage:

- Three-column workbench: Task 5.
- Vue 3 + Vite + Element Plus + Pinia + ECharts: Tasks 1, 2, 4.
- `/api/chat/query` with mock fallback: Task 2.
- Answer, SQL, safety, rows, execution time, retry, optimization suggestions: Tasks 2, 4, 5.
- Example questions, history, Schema overview: Tasks 2, 3, 5.
- Responsive layout: Tasks 5 and 6.
- Friendly error and empty states: Tasks 2, 4, 5.

Placeholder scan:

- No placeholder markers or undefined future-only steps are used.
- Every created file has concrete content.
- Every verification command includes expected output.

Type consistency:

- API response fields match the design spec: `answer`, `sql`, `is_sql_safe`, `columns`, `rows`, `execution_time_ms`, `retry_count`, `optimization_suggestions`.
- Store methods used in `Home.vue` are defined in `stores/query.js`: `submitQuestion` and `setQuestion`.
- Shared constants used in `Home.vue` are exported from `api/agent.js`: `exampleQuestions` and `schemaTables`.

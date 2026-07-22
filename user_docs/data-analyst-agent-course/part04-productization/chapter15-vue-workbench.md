# 第十五章 开发 Vue 数据分析工作台

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 15.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释 Vue 应用入口、Router、Pinia 和组件之间的关系；
> 2. 读懂查询 Store 的加载、成功、失败、取消和历史状态；
> 3. 理解 Axios 普通请求与原生 Fetch SSE 请求的差异；
> 4. 说明工作台如何展示答案、表格、图表、SQL、意图和审计；
> 5. 理解主动澄清、权限演示和主题切换如何接入现有状态；
> 6. 使用前端单测和生产构建验证组件契约。

## 15.2 问题场景：把 Agent 结果变成可用产品

> 后端响应包含自然语言答案、SQL、列和行、意图、澄清、审计和优化建议。如果前端只把 JSON 打印出来，用户仍然需要自己阅读结构化数据。
>
> 当前工作台采用三栏布局：左侧负责输入和上下文，中间负责答案、图表和表格，右侧负责意图、SQL、审计和优化。组件只通过 Props 接收结果，通过事件通知父组件或 Store，避免每个组件各自请求后端。

## 15.3 应用入口和路由

```javascript
const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

> `main.js` 创建 Vue 应用，注册 Pinia、Router、Element Plus 组件和 SQL 语法高亮，最后挂载到 `index.html` 的 `#app`。`App.vue` 只负责渲染 `<router-view />`，具体页面由路由决定。
>
> 把全局依赖放在入口可以让页面和组件只关注业务，不需要每个组件重复创建 Store 或 HTTP 客户端。

## 15.4 Axios API 客户端

```javascript
const client = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})
```

> 普通查询、Schema 获取和登录使用 Axios。拦截器统一添加 JWT，避免每个 API 函数重复拼接认证头。API 函数把后端响应压缩为页面需要的对象，并把 401 转换成用户可理解的错误。

## 15.5 为什么 SSE 使用 Fetch

> 当前 SSE 查询使用原生 `fetch()` 和 `ReadableStream.getReader()`，因为需要逐行读取服务端事件并支持 `AbortController`。它不能直接复用普通 Axios JSON 响应的解析方式。

```javascript
const reader = response.body.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n')
  buffer = lines.pop() || ''
  // 逐行处理 data: 事件
}
```

> 解析器保留最后一个不完整行，等待下一次网络块拼接。不能假设一次 `read()` 正好返回一个完整 JSON；网络分块与业务事件边界没有关系。

## 15.6 Pinia Query Store

### 15.6.1 状态

```javascript
const question = ref('')
const sessionId = ref(
  globalThis.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`,
)
const loading = ref(false)
const loadingStage = ref('')
const loadingProgress = ref(0)
const result = ref(null)
const error = ref(null)
```

> Store 是查询页面的单一状态源，保存问题、会话 ID、加载阶段、结果、错误、历史、收藏和取消控制器。组件通过 Store 读写状态，而不是互相调用 API。

### 15.6.2 提交和取消

```javascript
async function submitQuestion(nextQuestion = question.value, clarification = null) {
  const normalizedQuestion = nextQuestion.trim()
  if (!normalizedQuestion || loading.value) return

  loading.value = true
  error.value = null
  result.value = null
  // 调用普通 API 或 SSE
}

function cancelQuery() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
}
```

> Store 在请求开始时清理旧错误和结果，在 `finally` 中恢复加载状态。取消只影响当前前端请求，但后端也必须配合取消 Agent task；前后端取消是两个需要同时验证的边界。

### 15.6.3 历史和收藏

> 历史记录只保留最近 20 条，收藏使用 `localStorage` 持久化并限制数量。它们是前端体验数据，不等于后端的多轮 SessionStore；删除浏览器收藏不会删除后端会话。

## 15.7 Home 工作台布局

```text
Home.vue
├── 左栏
│   ├── QueryInput
│   ├── ExampleQuestions
│   ├── HistoryPanel
│   └── SchemaPanel
├── 中栏
│   ├── AnswerPanel
│   ├── ChartPanel
│   └── ResultTable
└── 右栏
    ├── IntentPanel
    ├── SQLPanel
    ├── AuditPanel
    └── OptimizationPanel
```

> `Home.vue` 负责组合组件和处理页面级事件，例如选择推荐问题、提交澄清候选、切换路由参数和更新页面标题。具体展示逻辑下沉到组件，查询状态下沉到 Store。

## 15.8 结果展示契约

> 后端 `QueryResponse` 的顶层字段包括 `sql`、`analysis_intent`、`optimization_suggestions`、`rows`、`answer`、`clarification` 和 `audit_report`。前端组件应直接消费当前契约，不能继续依赖已经移除的旧字段。

| 组件 | 主要字段 | 展示内容 |
|---|---|---|
| `AnswerPanel` | `answer`、执行指标 | 自然语言答案和耗时 |
| `ChartPanel` | `columns`、`rows` | 柱状、折线、饼图等 |
| `ResultTable` | `columns`、`rows` | 分页表格和导出 |
| `SQLPanel` | `sql` | 最终 SQL |
| `IntentPanel` | `analysis_intent`、`clarification` | 意图和澄清候选 |
| `AuditPanel` | `audit_report` | 身份、权限和 Guard 证据 |
| `OptimizationPanel` | `optimization_suggestions` | 优化建议 |

> 组件之间共享同一份 `result`，避免一个组件重复请求或重新解释响应。真实响应字段变化时，应先更新 Pydantic 契约、API fixture、Store 和相关组件测试。

## 15.9 图表和表格的边界

> `ChartPanel` 根据列类型和数据形状选择图表，`ResultTable` 负责表格分页、CSV/Excel 导出和空结果展示。当前 v1.7 的 Excel 导出使用 `frontend/src/utils/spreadsheet.js` 生成 SpreadsheetML 文本单元格，而不是把用户可控结果交给公式解释器；这是一条前端输出安全边界。图表是结果的可视化，不应该改变原始行数据或重新计算业务指标；指标计算应由 SQL 和语义层完成。
>
> 空结果、单列结果、日期字符串和数值字符串都可能出现。组件需要先检查数据形状，再决定是否显示图表，而不是假设每个查询都返回两列数值。

## 15.10 主动澄清和权限演示

```javascript
function handleClarification(option) {
  store.submitClarification(option)
}
```

> `IntentPanel` 展示候选并通过事件把候选对象交给 Store。Store 只把 `clarification_id` 和 `candidate_id` 送回后端，后端负责校验候选是否属于当前会话。
>
> `AuthBar` 支持本地演示角色切换，`AuditPanel` 展示权限允许或阻断证据。前端的角色按钮只是获得 Token 的入口，真正的权限仍由后端 Data Permission Guard 执行。

## 15.11 响应式、主题和无障碍注意点

> `main.css` 定义桌面、平板和移动端布局，`ThemeToggle` 切换暗色变量。组件应给按钮、输入框和状态标签提供清晰文本，加载中和错误状态不能只通过颜色区分。
>
> 视觉层可以改善体验，但不能替代数据状态。例如“DuckDB Connected”只说明 Schema 已加载，不代表当前用户有权访问所有数据；权限结果应该在审计面板中明确展示。

## 15.12 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `frontend/src/main.js` | Vue 应用入口 | Pinia、Router、组件和高亮 |
| `frontend/src/App.vue` | 根组件 | 路由出口 |
| `frontend/src/views/Home.vue` | 三栏工作台 | 组件组合和页面事件 |
| `frontend/src/api/agent.js` | 后端客户端 | Axios、SSE、响应解析 |
| `frontend/src/stores/query.js` | 查询状态 | 提交、取消、历史、收藏 |
| `frontend/src/components/AnswerPanel.vue` | 答案和指标 | 加载、错误和文本展示 |
| `frontend/src/components/ChartPanel.vue` | 图表 | 列行到 ECharts |
| `frontend/src/components/ResultTable.vue` | 结果表格 | 分页和导出 |
| `frontend/src/utils/spreadsheet.js` | Excel XML 导出 | XML 转义和公式注入防护 |
| `frontend/tests/utils/spreadsheet.test.js` | 导出安全测试 | 文本单元格和特殊字符 |
| `frontend/src/components/AuditPanel.vue` | 安全审计 | 权限和规则证据 |

## 15.13 动手验证

> 先运行前端单元测试和生产构建：

```bash
npm run test --prefix frontend
npm run build --prefix frontend
```

> 如果要专门验证导出边界，可运行：

```bash
npm run test --prefix frontend -- spreadsheet
```

> 如果需要运行浏览器端到端测试：

```bash
npm run test:e2e --prefix frontend
```

> 端到端测试需要 Playwright 浏览器和独占的前后端测试端口；它会验证工作台交互、响应式布局和权限演示。真实 LLM 不是前端组件测试的前置条件，测试可以使用共享 API fixture 或 Mock 响应。

## 15.14 常见错误

### SSE 事件被拆成半个 JSON

> 这是网络分块的正常现象。必须保留缓冲区最后一行，等下一块数据拼接；不要对每个 `read()` 的字符串直接 `JSON.parse()`。

### 页面显示不到 SQL 或意图

> 先检查后端响应是否包含当前 `QueryResponse` 字段，再检查 Store 是否把响应原样写入 `result`，最后检查组件 Props 名称。不要通过新增兼容空字段掩盖前后端契约漂移。

### 取消按钮只改变文字

> 前端需要调用 `AbortController.abort()`，后端还需要取消对应 Agent task。只改 `loadingStage` 不会停止模型或数据库工作。

### 前端角色切换看起来成功但查询仍越权

> 检查 Token 是否更新、请求拦截器是否带上 Authorization，以及后端审计中的 `user_id`、`roles` 和阻断规则。不要仅凭顶部标签判断权限已经改变。

## 15.15 本章小结

> Vue 工作台通过 API 客户端、Pinia Store 和组件树把后端的复杂状态转成可操作界面：用户输入问题、看到 SSE 进度、阅读答案和图表、检查 SQL 与意图、查看权限审计，并可以恢复澄清。前端负责展示和交互，后端仍是查询、安全和权限的事实来源。

## 15.16 练习

1. 从 `handleSubmit()` 追踪一次问题提交到 `queryAgentSSE()` 的调用路径。
2. 给空结果增加一条可理解的 UI 提示，并补充组件测试。
3. 说明为什么 `sessionId` 放在 Pinia Store，而不是每次请求随机生成。
4. 找出普通 Axios 查询和 SSE Fetch 请求添加认证头的不同位置。
5. 在审计面板中设计一个“权限被阻断”的最小展示，要求不暴露完整策略表达式。

## 15.17 下一章衔接

> 产品界面已经把核心链路呈现出来，但“看起来能用”还不能证明没有回归。下一部分会学习后端单测、前端单测、Playwright E2E、评测用例和质量门禁。

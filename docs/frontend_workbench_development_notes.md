# 前端工作台开发记录

这份文档记录本次前端开发做了什么、为什么这样做，以及你作为初学者可以按什么顺序学习代码。

## 1. 创建前端开发分支

本次前端开发创建了一个单独分支：

```bash
codex/frontend-workbench
```

这样做是为了把前端开发和后端开发隔离开。前端会新增很多文件，如果直接在 `main` 分支上开发，后续和后端合并时容易混乱。单独分支更适合独立开发和 review。

## 2. 搭建 Vue 前端工程

前端工程位于：

```text
frontend/
```

新增了这些基础文件：

```text
frontend/
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
└── src/
    ├── App.vue
    ├── main.js
    └── styles/
        └── main.css
```

这些文件让 `frontend/` 从一个空目录变成了可以运行和构建的 Vue 项目。

## 3. 使用的前端技术栈

本次前端按照 `docs/data_analyst_agent_开发文档_v_0_2.md` 使用以下技术：

| 技术 | 作用 |
|---|---|
| Vue 3 | 页面框架 |
| Vite | 前端启动和打包工具 |
| Element Plus | UI 组件库 |
| Pinia | 前端状态管理 |
| Axios | 调用后端 API |
| ECharts | 展示图表 |

这些技术共同组成一个正式的前端应用，而不是简单 HTML 页面。

## 4. API 层

新增文件：

```text
frontend/src/api/agent.js
```

这个文件负责调用后端接口：

```text
POST /api/chat/query
```

请求格式：

```json
{
  "question": "统计 2024 年每个月的销售额"
}
```

响应字段对齐开发文档 v0.2：

```json
{
  "question": "统计 2024 年每个月的销售额",
  "sql": "SELECT ...",
  "is_sql_safe": true,
  "columns": ["month", "sales"],
  "rows": [],
  "answer": "2024 年每个月销售额如下...",
  "execution_time_ms": 42,
  "retry_count": 0,
  "optimization_suggestions": []
}
```

因为后端完整 Agent 接口还没有完全联调，所以这里加入了 mock fallback：

- 后端接口可用时，展示真实后端结果。
- 后端接口不可用时，展示模拟数据，保证前端页面可以先预览。

这样前端开发不会被后端进度卡住。

## 5. 状态管理

新增文件：

```text
frontend/src/stores/query.js
```

这个文件使用 Pinia 管理页面状态：

| 状态 | 含义 |
|---|---|
| `question` | 当前输入的问题 |
| `loading` | 是否正在请求 |
| `result` | 当前查询结果 |
| `error` | 当前错误信息 |
| `history` | 查询历史 |

这样做的好处是：多个组件可以共享同一份状态，不需要在组件之间反复传递数据。

## 6. 页面组件

本次把页面拆成多个组件，每个组件只负责一个清晰职责。

```text
frontend/src/components/
├── QueryInput.vue
├── ExampleQuestions.vue
├── HistoryPanel.vue
├── SchemaPanel.vue
├── AnswerPanel.vue
├── ChartPanel.vue
├── ResultTable.vue
├── SQLPanel.vue
└── OptimizationPanel.vue
```

组件职责：

| 组件 | 作用 |
|---|---|
| `QueryInput.vue` | 自然语言输入框和“开始分析”按钮 |
| `ExampleQuestions.vue` | 示例问题 |
| `HistoryPanel.vue` | 查询历史 |
| `SchemaPanel.vue` | 数据库表结构简览 |
| `AnswerPanel.vue` | 自然语言解释 |
| `ChartPanel.vue` | ECharts 图表 |
| `ResultTable.vue` | 查询结果表格 |
| `SQLPanel.vue` | 生成 SQL 和 SQL 安全状态 |
| `OptimizationPanel.vue` | 执行耗时、retry 次数、优化建议 |

拆组件的目的，是让代码更容易阅读和维护。你学习时可以一个组件一个组件看。

## 7. 首页布局

主要页面文件：

```text
frontend/src/views/Home.vue
```

首页采用三栏工作台布局：

```text
左侧：输入问题、示例问题、历史记录、Schema 简览
中间：结果解释、图表、表格
右侧：SQL、安全状态、优化建议
```

这个布局既符合现代 AI 工具的使用习惯，也能展示本项目的核心闭环：

```text
自然语言问题
  → 生成 SQL
  → SQL 安全校验
  → 执行查询
  → 返回表格和图表
  → 生成自然语言解释
  → 展示优化建议
```

## 8. 全局样式

主要样式文件：

```text
frontend/src/styles/main.css
```

样式方向：

- 浅色背景。
- 白色面板。
- 8px 左右圆角。
- 蓝绿色作为主色。
- SQL 使用浅色代码块。
- 页面支持响应式布局。

目标不是做花哨大屏，而是做一个清爽、专业、易用的数据分析工具界面。

## 9. 验证方式

安装依赖：

```bash
cd frontend
npm install
```

启动开发服务器：

```bash
cd frontend
npm run dev
```

浏览器访问：

```text
http://localhost:3000
```

生产构建：

```bash
cd frontend
npm run build
```

本次验证结果：

- 页面可以打开。
- mock 数据可以展示。
- 图表可以渲染。
- 表格可以展示。
- SQL 面板可以展示。
- 浏览器控制台没有 error。
- `npm run build` 成功。

构建时有一个 chunk size 警告，主要来自 Element Plus 和 ECharts。第一版可以接受，后续需要优化包体时再做按需加载。

## 10. Git 提交记录

本次前端开发按阶段提交：

```text
ab731a2 feat: scaffold Vue frontend
73c20ff feat: add frontend query state
7230d1d feat: add workbench sidebar components
a3c9fcf feat: add analysis result components
76d716b feat: compose frontend workbench
a716391 feat: compose frontend workbench
2f0ad4a docs: update work diary for frontend workbench
```

分阶段提交的好处是：以后你可以通过 Git 历史回看每一步做了什么。

## 11. 推荐学习顺序

如果你想学习这次前端代码，建议按这个顺序看：

1. `frontend/src/views/Home.vue`

   先看首页怎么把所有组件组合起来。

2. `frontend/src/stores/query.js`

   再看 Pinia 如何管理问题、加载状态、结果、错误和历史。

3. `frontend/src/api/agent.js`

   理解前端如何调用后端，以及 mock fallback 怎么工作。

4. `frontend/src/components/QueryInput.vue`

   看输入框和提交按钮如何触发查询。

5. `frontend/src/components/ResultTable.vue`

   看后端的 `columns` 和 `rows` 如何转换成表格。

6. `frontend/src/components/ChartPanel.vue`

   看查询结果如何转换成 ECharts 图表。

7. `frontend/src/components/SQLPanel.vue`

   看 SQL 和安全状态如何展示。

8. `frontend/src/components/AuditPanel.vue`

   看安全审计摘要和生成、校验、执行事件如何展示。

9. `frontend/src/styles/main.css`

   最后看布局和视觉样式。

## 12. 后续和后端如何联调

前端已经按开发文档 v0.2 的 API 契约开发：

```text
POST /api/chat/query
```

前端已经接入后端 `session_id` 和 `audit_report`。工作台会在页面生命周期内复用同一个会话 ID，并优先使用真实接口。如果字段有小差异，只需要改：

```text
frontend/src/api/agent.js
```

页面组件通常不需要大改。

## 13. 本次开发总结

本次完成的核心事情是：

```text
把空的 frontend 目录，开发成了一个可运行、可展示、后续可接后端的 Vue 数据分析工作台。
```

这个前端现在已经具备第一版展示能力：

- 用户可以输入自然语言问题。
- 页面可以展示 SQL。
- 页面可以展示 SQL 安全状态。
- 页面可以展示查询结果表格。
- 页面可以展示图表。
- 页面可以展示自然语言解释。
- 页面可以展示优化建议。
- 页面会持续发送 `session_id`，支持多轮追问。
- 页面可以展示安全审计摘要和事件时间线。

当前可以直接与后端 `/api/chat/query` 进行真实联调；接口不可用时仍保留 mock fallback 用于前端预览。

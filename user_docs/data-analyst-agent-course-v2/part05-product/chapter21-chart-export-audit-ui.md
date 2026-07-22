# 第21章 图表、导出与审计界面

> 本章预计 1～2 小时，学习把同一结构化结果变成可验证、可视化、可导出和可解释的界面。测试使用固定数据。

## 21.1 学习目标

> 能解释图表自动检测、ECharts 生命周期、连续查询 dispose、表格分页、CSV/SpreadsheetML 转义、公式注入防护和审计摘要展示。

## 21.2 前置知识

> 已理解 QueryResponse、Vue computed/watch/lifecycle、HTML 下载与第18章 AuditReport。

## 21.3 为什么需要这一模块

> 自然语言答案便于阅读，但 SQL、表格和审计证据帮助核验；图表帮助发现关系；导出支持后续使用。展示层不能悄悄改变数据，也不能把用户可控单元格变成电子表格公式。

## 21.4 输入、输出与依赖

| 组件 | 输入 | 输出/行为 |
|---|---|---|
| ResultTable | columns、rows | 分页、CSV/XML下载 |
| ChartPanel | columns、rows | ECharts option |
| AuditPanel | audit_report | 安全/权限/事件证据 |

> 三者读取同一个浏览器结果，不再次执行 SQL。导出包含当前完整 rows，不只是当前分页。

## 21.5 执行流程

```text
QueryResponse
  ├─ ResultTable → sanitize → neutralize formula → CSV/XML → Blob
  ├─ ChartPanel  → detect type → option → ECharts lifecycle
  └─ AuditPanel  → computed summaries → tags/events
```

## 21.6 当前代码地图

| 内容 | 路径 |
|---|---|
| 图表 | `frontend/src/components/ChartPanel.vue` |
| 表格 | `frontend/src/components/ResultTable.vue` |
| 审计 | `frontend/src/components/AuditPanel.vue` |
| 导出 | `frontend/src/utils/spreadsheet.js` |
| 图表测试 | `frontend/tests/components/ChartPanel.test.js` |
| 导出测试 | `frontend/tests/utils/spreadsheet.test.js` |

## 21.7 关键代码理解

### 21.7.1 图表类型是展示推断

> ChartPanel 根据列数与数值特征选择自动类型，用户可切换。图表配置不改变 SQL 结果，任何聚合都应在后端查询中明确完成。

### 21.7.2 ECharts 生命周期

> 结果清空、DOM 替换或组件卸载时必须 dispose 旧实例并清引用；动态加载 ECharts 后还要重新确认当前容器。连续查询若复用旧 DOM 实例，会导致第二次图表空白或指向失效节点。

### 21.7.3 公式注入

> 以 `= + - @` 开头的单元格在 Excel 中可能执行公式。导出先移除非法控制字符，再在前面加单引号；CSV 还转义引号/逗号/换行，SpreadsheetML 还转义 XML 字符，并把所有值声明为 String。

### 21.7.4 审计面板不做权限决策

> AuditPanel 只展示后端产生的 permission decision、row filters、blocked rules 和 events。前端不能通过隐藏标签改变 authorized SQL，也不应显示 Token/Key/完整 Prompt。

## 21.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
npm run test --prefix frontend -- --run tests/components/ChartPanel.test.js tests/utils/spreadsheet.test.js
npm run build --prefix frontend
```

## 21.9 故障注入实验

> 依次给 ChartPanel 结果A、空结果、结果B，确认旧实例 dispose 且B重新 init；给导出单元格 `=1+1`、带引号换行和 XML 特殊字符，确认不执行公式且文件结构有效。

## 21.10 调试路径与常见误判

> 图表空白按 props→computed option→容器→ECharts加载→instance/resize 检查。下载成功只证明 Blob 产生，不证明编码、转义和公式安全。审计显示允许也不能替代后端日志/评测证据。

## 21.11 独立编码练习

> 为表格导出设计“当前页/全部行”的明确交互，并为公式、Unicode、NULL、换行和超大行数写验收标准，不直接复制生产代码。

## 21.12 测试或评测验证

> 覆盖连续查询、类型切换、主题、resize、unmount、CSV quoting、XML escaping、formula neutralization，以及表格/图表/审计同源字段。

## 21.13 面试复述题

> 1. 为什么答案之外要保留 SQL、表格和审计？
>
> 2. 连续查询图表空白的生命周期根因是什么？
>
> 3. 电子表格公式注入如何防护？

## 21.14 掌握度检查与下一章

> 能定位图表生命周期；能手算CSV/XML转义；能说明AuditPanel的只读边界。下一章完成部署与 readiness。

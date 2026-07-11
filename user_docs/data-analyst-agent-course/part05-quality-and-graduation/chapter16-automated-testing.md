# 第十六章 后端、前端与端到端测试

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 16.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释测试金字塔中单元、集成和端到端测试的区别；
> 2. 读懂 pytest fixture 如何准备隔离数据；
> 3. 识别哪些边界应该 Mock，哪些核心行为必须真实执行；
> 4. 使用 Vitest 测试 Vue Store 和组件；
> 5. 使用 Playwright 验证页面交互和权限演示；
> 6. 判断“测试数量很多”和“系统可靠”之间的差距。

## 16.2 问题场景：为什么要多层测试

> Data Analyst Agent 既有纯函数和规则，也有数据库、LLM、LangGraph、HTTP 和浏览器。只运行一种测试无法覆盖全部风险：规则测试很快但看不到真实 API 契约，端到端测试接近用户但慢且容易受环境影响。

| 层级 | 主要对象 | 反馈速度 | 适合发现 |
|---|---|---:|---|
| 单元测试 | 解析器、Guard、格式化器、Store 函数 | 快 | 局部逻辑错误 |
| 集成测试 | AgentGraph、数据库、API 契约 | 中 | 模块连接和状态分支 |
| E2E 测试 | 浏览器、前端、Mock 后端或测试服务 | 慢 | 页面交互、路由和响应式问题 |
| 评测 | 固定业务问题和质量指标 | 更慢 | 模型行为、正确性和安全回归 |

> 测试层级不是替代关系。核心安全不变量应在快速单测和 AgentGraph 集成测试中都有覆盖，关键用户路径再由 E2E 验证。

## 16.3 问题场景：测试环境也需要隔离

> `backend/tests/conftest.py` 提供测试共享配置。数据库相关测试使用临时路径或注入连接，避免把开发者本机的 `data/database.duckdb` 当作测试事实来源。
>
> fixture 的价值是统一准备和清理资源。一个 fixture 应该有清晰的生命周期，不能在测试之间隐式共享会被修改的列表、数据库连接或会话状态。

## 16.4 后端单元测试例子

> `test_sql_guard.py` 可以直接把输入 SQL 交给 Guard，验证语句类型、危险函数、LIMIT 和审计事件；它不需要启动 HTTP 服务，也不需要调用模型。

```python
def test_blocks_delete():
    result = sql_guard.validate("DELETE FROM orders")
    assert result["is_safe"] is False
    assert result["blocked_rule"] == "block_statement_type"
```

> 这种测试的断言应该关注稳定行为和规则 ID，而不是依赖完整错误原文。错误文本可能为了隐私或可读性调整，规则 ID 和安全结论更适合长期回归。

## 16.5 AgentGraph 集成测试

> 工作流测试可以在 LLM 边界注入 `AsyncMock`，但仍运行真实的节点路由和状态更新。例如成功路径应经过优化和答案节点，Guard 拒绝应不调用 Repair，权限阻断应不调用 QueryRunner。

```text
Fake LLM
  + 真实 AgentGraph
  + 真实 Guard
  + 隔离数据库
  → 验证完整编排行为
```

> 这种测试不是对真实模型质量的证明，而是对“当模型返回这个确定结果时，系统是否正确处理”的证明。真实模型评测需要第十七章的 case 和报告。

## 16.6 API 契约测试

> `QueryResponse` 设置了 `extra="forbid"`，前后端契约测试会阻止旧字段悄悄混入。测试应覆盖正常结果、阻断、澄清、权限失败和重试耗尽的稳定响应结构。
>
> API 测试的重点不是把每个内部函数再测一遍，而是确认 HTTP 输入、认证依赖、AgentGraph 输出和 Pydantic 响应之间没有字段漂移。

## 16.7 Vitest 前端单测

> `frontend/vitest.config.js` 使用 `happy-dom` 和 Vue 插件。前端测试可以通过组件挂载、Store 调用和 Mock API 验证交互，不需要启动真实模型。

```bash
npm run test --prefix frontend
```

> 常见测试对象包括 QueryInput 提交/取消、ResultTable 分页、AnswerPanel 空状态、AuthBar 角色切换和 AuditPanel 审计展示。测试应断言用户可观察行为，而不是只断言某个内部变量被赋值。

## 16.8 Playwright E2E

> `frontend/playwright.config.js` 为 E2E 配置独占后端和前端端口，默认启动 Uvicorn 和 Vite，并使用 `--strictPort` 避免误连开发者已占用的服务。CI 中可通过环境变量切换管理服务模式。

```bash
npm run test:e2e --prefix frontend
```

> E2E 覆盖工作台基础交互、响应式布局和权限演示。它的价值在于验证浏览器真实事件、路由、组件组合和 API 响应，但失败时需要先排查端口、浏览器、服务启动和网络代理，再判断业务代码。

## 16.9 测试替身的边界

| 可以 Mock | 不应长期 Mock 掉 |
|---|---|
| 外部 LLM 网络响应 | AgentGraph 条件边 |
| 当前测试不关心的时间或随机数 | SQL Guard 和权限 Guard |
| E2E 的后端响应 fixture | 前端到响应字段的真实映射 |
| 远程服务和昂贵评测 | 隔离数据库中的核心查询行为 |

> Mock 的目标是控制不稳定外部依赖，而不是让测试绕过系统最重要的业务规则。每次新增 Mock 都要说明它替代了什么，以及哪一层测试会覆盖真实行为。

## 16.10 代码地图

| 文件或目录 | 作用 | 阅读重点 |
|---|---|---|
| `backend/tests/conftest.py` | 后端共享 fixture | 隔离数据库、环境和客户端 |
| `backend/tests/test_agent_graph.py` | 工作流集成测试 | 成功、Guard、权限、修复和澄清 |
| `backend/tests/test_core_path_cases.py` | 核心路径配置测试 | case 结构、来源链接和演示顺序 |
| `frontend/vitest.config.js` | 前端单测配置 | happy-dom、别名和排除目录 |
| `frontend/tests/` | Vue 组件、Store 和 API 测试 | 用户可观察行为 |
| `frontend/playwright.config.js` | E2E 配置 | 独占端口、浏览器和重试 |
| `frontend/e2e/` | 浏览器场景 | 工作台、响应式和权限演示 |

## 16.11 动手验证

> 运行后端核心路径测试：

```bash
pytest backend/tests/test_core_path_cases.py -q
```

> 运行前端单测和构建：

```bash
npm run test --prefix frontend
npm run build --prefix frontend
```

> 环境具备 Playwright 浏览器时再运行 E2E。不要把 E2E 因本机没有浏览器而失败，误写成业务逻辑失败；应记录实际环境条件。

## 16.12 常见错误

### 测试互相污染

> 典型症状是单独运行通过、并行运行失败，或测试结果依赖执行顺序。检查全局 SessionStore、缓存数据库、环境变量和临时 DuckDB 是否被多个进程共享。

### 只断言“没有异常”

> 没有异常不代表返回正确。安全测试还应断言规则 ID、没有调用下游依赖、没有写入会话和最终状态字段。

### E2E 误连本地服务

> 如果没有 strict port，测试可能使用开发者手动启动的另一套服务。检查 `E2E_BACKEND_PORT`、`E2E_FRONTEND_PORT` 和 `reuseExistingServer: false`。

### 过度 Mock

> Mock 让测试很快，但如果所有 Agent 节点都被 Mock，路由错误永远不会暴露。至少保留一组真实工作流和隔离数据库的集成测试。

## 16.13 本章小结

> 单元测试锁定局部规则，集成测试验证模块连接，E2E 验证浏览器路径，评测则衡量模型和业务结果。高质量测试不是追求一个漂亮的数量，而是让每个重要不变量在合适的层级有证据。

## 16.14 练习

1. 为一个 SQL Guard 规则设计单元测试和 AgentGraph 集成测试各一条。
2. 找出一个不适合使用真实 LLM 的前端测试，并说明应替换哪一层。
3. 让一个测试故意复用全局 SessionStore，观察并发或顺序污染现象。
4. 解释为什么 E2E 的独占端口属于测试可靠性，而不是业务功能。
5. 阅读核心路径测试，列出它与普通 YAML 结构测试的区别。

## 16.15 下一章衔接

> 测试可以验证预先写好的行为，但还需要用一组固定业务问题衡量 NL2SQL 的成功率、正确率、安全率和修复率。下一章会进入评测数据集、报告和质量门禁。

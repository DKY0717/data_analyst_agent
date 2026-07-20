# 第30章 实战二：端到端调试实验室

> 本章预计 1～2 小时。你将用四个可恢复故障练习“先分类、再取证、最后最小修复”，而不是看到 Agent 异常就随机改 Prompt。

## 30.1 学习目标

> 完成本章后，你应该能够：
>
> - 保存最小复现所需的问题、身份、session、request ID 和环境；
> - 沿前端 → API → Agent state/event → Guard → DB/LLM 边界定位；
> - 分别处理工作目录错误、Schema/字段错误、权限误判和空 content；
> - 区分用户错误、业务阻断、可修复执行错误和基础设施错误；
> - 输出一份可以让别人复查的调试报告。

## 30.2 前置知识

> 你已经完成前六部分，能运行后端测试、前端测试和构建，并知道日志不能输出 Key、完整 token 或敏感查询结果。

## 30.3 为什么需要这一模块

> Agent 链路长，表面现象常与根因相距多个节点。“页面没有结果”可能是前端状态没更新、API 返回澄清、权限合法拒绝、SQL 列错误进入 Repair、数据库路径错，或 LLM 没有返回 content。
>
> 高质量调试不是猜中答案，而是用最少实验逐层排除。每次只改变一个变量，并让修复后的回归测试永久捕获这个故障。

## 30.4 输入、输出与依赖

### 最小输入包

> 每次调试至少保存以下非敏感信息：
>
> - 原始问题和预期业务结果；
> - 角色/scopes，但不保存 token；
> - 是否同步或 SSE、是否带 session/clarification；
> - HTTP 状态、业务 `code`、request ID；
> - 当前 HEAD、数据库类型、启动目录；
> - 最后成功节点、首个失败节点、稳定错误类型；
> - 最小日志片段，删除 Key、完整 SQL 结果和供应商原文。

### 输出

> 输出不是一句“已修好”，而是最小复现、根因证据、被排除假设、最小改动、回归测试和剩余风险。

## 30.5 执行流程

```text
冻结输入与环境
  → 在最小边界复现
  → 判断前端 / HTTP / Agent / DB / LLM
  → 找到最后一个正确输出
  → 检查下一个边界的输入与输出
  → 用替身隔离不稳定依赖
  → 形成单一根因假设
  → 用可逆实验证伪/证实
  → 做最小修复
  → 新增回归测试
  → 跑相邻与全链路验证
```

> 若无法稳定复现，先增加脱敏观测，不要同时改 parser、Prompt 和前端。多层一起改会让你无法知道哪个变化真正解决问题。

## 30.6 当前代码地图

| 边界 | 路径 | 首要证据 |
|---|---|---|
| 前端状态 | `frontend/src/stores/query.js` | loading/error/result/session |
| 前端请求 | `frontend/src/api/agent.js` | HTTP/SSE 事件与取消 |
| API | `backend/app/api/query.py` | response code、SSE terminal event |
| Agent 编排 | `backend/app/agents/graph.py` | state 字段与条件边 |
| Intent/Grounding | `backend/app/analysis_intent/`、`backend/app/agents/grounding.py` | slots、candidate、route |
| SQL 安全/权限 | `backend/app/security/` | rule ID、authorized SQL changed |
| Schema/执行 | `backend/app/db/schema_loader.py`、`backend/app/db/query_runner.py` | 当前物理列与执行错误类型 |
| LLM | `backend/app/services/llm_service.py` | HTTP、content、attempt、latency |
| 审计/追踪 | `backend/app/agents/audit.py`、`backend/app/services/tracing.py` | request-scoped 稳定证据 |

## 30.7 关键代码理解

### 调试总原则：最后正确边界 + 第一个错误边界

> 假设 Intent 中 metric/dimension 正确、Grounding route 错，那么 parser 不是首要修复点。假设 API JSON 正确、Pinia store 没写入，则不应修改 Agent。只有找到相邻两个边界，根因才足够窄。

### 故障 A：工作目录错误

> **注入：** 在项目根目录直接运行本应从 `backend` 目录执行的模块命令，或从错误目录启动 uvicorn。常见现象包括 `ModuleNotFoundError: app`、相对配置/数据库路径不对、服务启动但读取到错误文件。
>
> **定位：** 记录 `Get-Location`、命令、`PYTHONPATH` 和目标文件是否存在。对照 README/AGENTS 中的运行目录，不要先安装随机包。
>
> **恢复：** 回到明确目录运行；测试命令优先从仓库根目录使用完整路径，模块入口按文档进入 backend。恢复不需要改业务代码。

```powershell
Get-Location
Test-Path backend/app/main.py
Set-Location backend
python -c "import app; print(app.__file__)"
Set-Location ..
```

### 故障 B：Schema 或字段不一致

> **注入：** 让 Fake LLM 生成 `SELECT revenue FROM orders`。预期 SQL Guard 可能认为它是安全 SELECT，但数据库会因未知列失败，随后按 Agent 条件进入 Repair。
>
> **定位：** 对比 SchemaLoader 的当前列、generated/validated/authorized SQL、execution_error 和 retry_count。若 Schema 本身未更新，先修迁移/种子；若模型引用错列，修语义/Prompt/Repair 契约。
>
> **恢复：** 用隔离数据库和 Fake Repair 输出 `total_amount`，确认修复后重新过 SQL Guard 与权限 Guard，再执行。不要在生产数据库临时创建错误列来“兼容模型”。

### 故障 C：把权限拒绝误判为系统故障

> **注入：** 使用 analyst 查询 `customers.customer_name` 或 `payments.paid_amount`。页面无结果，但预期是权限层阻断，不是 QueryRunner 失败。
>
> **定位：** 检查 identity roles/scopes、`permission_allowed`、`permission_error`、authorization event 和 blocked rule；确认 QueryRunner 与 Repair 没被调用。再用 admin 做对照，验证同一 SQL在授权身份下能执行。
>
> **恢复：** 如果策略符合业务，不修代码，只改善用户提示；若业务确认应该允许，再最小修改 YAML 策略并补 analyst/admin/support 回归。绝不能在 Graph 中跳过权限节点。

### 故障 D：LLM reasoning 非空但 content 为空

> **注入：** HTTP Mock 返回 OpenAI-compatible 外壳，`reasoning_content` 有值但 `content` 为空。不得调用真实供应商做故障注入。
>
> **定位：** 检查 HTTP 200、choices/message 结构、content、reasoning 长度、attempt 和外层耗时。第 28 章已证明基线循环在该路径可能不受普通重试预算终止。
>
> **恢复目标：** 所有可重试分支共享明确总预算或 deadline；耗尽后返回稳定错误；reasoning 不进入业务 JSON。回归测试必须连续返回空 content，证明不会依赖 Actions 外层超时。

### 可选故障 E：SSE 中断但后端仍工作

> 让前端取消请求或模拟 EventSource/Fetch 流中断，观察 store 是否清理 loading、后端是否收到取消、最终状态是否被旧请求覆盖。它用于练习跨前后端边界，不要与前四个故障同时注入。

## 30.8 最小动手运行

> 先验证 API、Graph、Tracing 和前端 store 的现有契约。

```powershell
pytest backend/tests/test_query_api.py backend/tests/test_agent_graph.py backend/tests/test_tracing.py -q
npm run test --prefix frontend -- tests/stores/query.test.js
```

> 然后每次只选一个故障，在对应测试文件的临时 fixture 中复现。不要改 `.env` 中真实 Key，也不要连接生产数据库。

## 30.9 故障注入实验

> 按下表完成四次实验，每次结束都恢复改动并写一页记录。

| 实验 | 可逆注入 | 预期首个失败边界 | 不应该修改 |
|---|---|---|---|
| A | 错误 cwd | 进程导入/配置 | Prompt、Schema |
| B | 未知列 `revenue` | QueryRunner 后进入 Repair | 数据权限策略 |
| C | analyst 查敏感列 | Permission Guard | SQL Guard 白名单 |
| D | reasoning 有值、content 空 | LLM Service | ResultComparator |

> 每次先写“如果假设成立，我会看到什么”，再运行实验。结果与预期不一致时，更新假设，不要硬解释。

## 30.10 调试路径与常见误判

> 用户说“空结果”时，先判断是空 rows、无 result 字段、clarification、blocked、execution failed、answer degraded，还是前端没有渲染。它们在结构化状态中应是不同语义。
>
> 常见误判一：HTTP 200 就是业务成功。API 可能在 200 中返回澄清或结构化业务状态。
>
> 常见误判二：SQL Guard 通过就表示列存在。Guard 主要检查安全 AST，不替代物理 Schema 执行验证。
>
> 常见误判三：没有结果就是数据库错误。权限拒绝、Intent 阻断和澄清本来就不应执行。
>
> 常见误判四：reasoning 有字就是模型成功。结构化任务必须有可消费 content。
>
> 常见误判五：改 Prompt 后现象消失就是根因已修复。没有固定替身回归，可能只是一次采样差异。

## 30.11 独立编码练习

> 为任一实验输出以下调试报告。报告中不要粘贴 Key、token、完整敏感 SQL 结果或供应商原始响应。

```markdown
# 调试报告：<短标题>

## 环境与版本
- HEAD：
- 启动目录/命令：
- DB/provider（不含密钥）：

## 最小复现
- 输入：
- 身份：
- 预期：
- 实际：

## 边界证据
- 最后正确节点：
- 第一个错误节点：
- 稳定错误类型/rule ID：

## 已排除假设
1.
2.

## 根因
- 代码/配置位置：
- 为什么能解释全部现象：

## 最小修复与回滚
- 修改：
- 回滚：

## 回归证据
- 新增测试：
- 相邻测试：
- 剩余风险：
```

> 面试时这份报告比“我很快修了一个 bug”更有说服力，因为它展示了定位方法和证据纪律。

## 30.12 测试或评测验证

> 修复后先运行新增的单条回归，再运行相邻模块，最后按风险扩大。示例层级如下：

```powershell
pytest backend/tests/test_llm_service.py -q
pytest backend/tests/test_agent_graph.py backend/tests/test_query_api.py -q
npm run test --prefix frontend
npm run build --prefix frontend
```

> 若修改安全、权限或执行路径，还要运行对应 evaluator 和核心路径。若只修 cwd 文档，则不应谎称跑了真实模型评测。

## 30.13 面试复述题

> **问题：用户说 Agent 给了空结果，你怎么定位？**
>
> 合格回答：先固定请求、身份、session、HEAD 和响应；区分空 rows、澄清、阻断、执行失败与前端未渲染；从浏览器 Network/API 契约进入 Agent state，找最后正确节点和第一个错误节点；用 Fake LLM/隔离 DB 复现，做最小修复和回归。
>
> **追问：什么时候不应该修代码？**
>
> 应回答：工作目录/启动命令错误先修运行方式；权限策略符合业务时，阻断是正确行为，只需改善提示；没有稳定复现时先补观测，不应随机改多层。

## 30.14 掌握度检查与下一章

> 如果你能在 15 分钟内把四个实验分别定位到运行环境、QueryRunner/Repair、Permission Guard 和 LLM Service，并说出相邻回归，就算掌握本章。
>
> 下一章不再依赖现有 12 节点 Graph，从空目录用 6 个小接口重建最小安全 NL2SQL 闭环。

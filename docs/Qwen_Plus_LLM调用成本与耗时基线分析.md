# Qwen Plus LLM 调用成本与耗时基线分析

## 1. 为什么增加 LLM 可观测性

NL2SQL Agent 的数据库执行通常只需要几毫秒，但用户实际等待时间主要来自 LLM。只展示 SQL 是否正确，无法回答生产环境中更关键的问题：

- 一次分析调用几次模型。
- SQL 生成、Repair 和答案生成分别消耗多少 Token 与时间。
- 修复重试会增加多少调用成本。
- 批量评测整体需要多少资源。

本项目在 Qwen API 边界记录真实 DashScope usage、逻辑调用总耗时和 API 尝试次数，并通过 `ContextVar` 隔离并发异步请求。指标不包含 API Key、请求头、完整 prompt、数据库 Schema、查询结果或完整原始响应。

## 2. 指标链路

```text
Qwen API Response
  -> 解析 usage、耗时、尝试次数
  -> ContextVar 隔离当前请求调用轨迹
  -> AgentState.llm_calls
  -> audit_report.llm_observability
  -> NL2SQL / Repair 离线评测报告
```

每次调用记录：

- 节点：`generate_sql`、`repair_sql` 或 `generate_answer`
- 模型名称
- 输入、输出和总 Token
- LLM 调用耗时
- API 尝试次数
- 成功状态与失败异常类型
- 可选估算成本

成本单价不硬编码。只有同时配置以下环境变量时才计算金额：

```text
QWEN_INPUT_PRICE_PER_MILLION_TOKENS
QWEN_OUTPUT_PRICE_PER_MILLION_TOKENS
```

本次本地基线没有配置价格，因此所有成本字段为 `null`，不会把未知成本显示为 0。

## 3. Qwen Plus 32 条 NL2SQL 真实基线

报告：

- `backend/evaluation/reports/nl2sql-evaluation-2026-06-10-094021.md`
- `backend/evaluation/reports/nl2sql-evaluation-2026-06-10-094021.json`

### 3.1 LLM 资源指标

| 指标 | 结果 |
|---|---:|
| 总 case 数 | 32 |
| LLM 总调用数 | 57 |
| LLM 总 Token | 60,457 |
| LLM 总耗时 | 297,632 ms |
| 平均每 case 调用数 | 1.78 |
| 平均每 case Token | 1,889.28 |
| 平均每 case LLM 耗时 | 9,301 ms |
| 平均数据库执行耗时 | 2.44 ms |
| 估算总成本 | 未配置价格 |

LLM 平均耗时约为数据库执行耗时的数千倍，说明当前端到端体验的主要性能瓶颈不是 DuckDB，而是模型调用和答案生成。

### 3.2 正常分析与危险请求差异

| 类型 | case 数 | 平均调用数 | 平均 Token | 平均 LLM 耗时 |
|---|---:|---:|---:|---:|
| 正常分析 | 24 | 2.00 | 2,049.21 | 11,226.96 ms |
| 危险请求 | 8 | 1.13 | 1,409.50 | 3,523.13 ms |

正常分析通常调用两次模型：一次生成 SQL，一次生成自然语言答案。被 Guard 阻断的危险请求不会进入答案生成，因此通常只有一次 SQL 生成调用，资源消耗明显更低。

### 3.3 效果与安全结果

| 指标 | 结果 |
|---|---:|
| 正常分析执行成功率 | 24/24，100% |
| 危险请求阻断率 | 7/8，87.5% |
| 安全预期命中率 | 31/32，96.9% |
| SQL 生成成功率 | 31/32，96.9% |

本轮唯一未满足危险请求阻断预期的 case 是读取本地文件请求。模型没有生成 `read_csv_auto`，而是把请求改写成一条无害的拒绝说明 `SELECT`，因此 SQL Guard 没有命中阻断规则，查询也没有访问文件。

这个结果说明：

1. LLM 的安全拒绝能够降低风险，但它不是稳定、可审计的程序级阻断。
2. 当前安全评测严格要求危险意图被 Guard 阻断，因此将该 case 记录为未命中。
3. 真实 LLM 具有随机性，安全基线需要持续运行，不能只展示最好的一次结果。

## 4. Qwen Plus 6 条 SQL Repair 真实基线

报告：

- `backend/evaluation/reports/sql-repair-evaluation-2026-06-10-094059.md`
- `backend/evaluation/reports/sql-repair-evaluation-2026-06-10-094059.json`

| 指标 | 结果 |
|---|---:|
| 总 case 数 | 6 |
| 端到端修复成功率 | 6/6，100% |
| 平均每 case LLM 调用数 | 1.00 |
| LLM 总 Token | 5,254 |
| 平均每 case Token | 875.67 |
| LLM 总耗时 | 23,175 ms |
| 平均每 case LLM 耗时 | 3,862.50 ms |
| 平均修复后数据库执行耗时 | 1.17 ms |
| 估算总成本 | 未配置价格 |

一次 Repair 平均增加约 `876 Token` 和 `3.86 秒` LLM 延迟。相比数据库执行时间，Repair 的主要成本同样来自模型调用，而不是重新执行 SQL。

## 5. 面试可讲结论

1. **不是只统计请求总耗时**：在 Qwen API 边界读取真实 usage，并区分数据库执行耗时与 LLM 耗时。
2. **并发指标不会串数据**：全局 Qwen 客户端使用 `ContextVar` 隔离异步请求轨迹，LangGraph state 负责跨节点传递。
3. **成本口径可维护**：价格通过环境变量配置，未配置时成本为 `null`，不硬编码可能变化的模型价格。
4. **Repair 成本可量化**：一次确定性 Repair 平均增加约 876 Token 和 3.86 秒。
5. **评测保留真实波动**：本轮危险请求阻断率为 87.5%，如实记录模型将危险请求改写成无害拒绝 SQL 的边界。

## 6. 当前边界与下一步

- 当前指标在单进程内随请求返回和写入报告，没有接入持久化时序监控。
- 成本是基于 Token 单价的估算值，不包含缓存、折扣、网络或其他计费规则。
- LLM 总耗时包含重试与退避等待，适合衡量用户实际等待，但不是纯服务端推理时间。
- 下一步可把测试和安全评测接入 GitHub Actions，并对安全基线下降设置 CI 阈值。

## 7. v0.4 Intent Guard 后复测（2026-06-11）

最新报告：

- `backend/evaluation/reports/unsafe-intent-evaluation-2026-06-11-092504.json`
- `backend/evaluation/reports/nl2sql-evaluation-2026-06-11-093035.json`
- `backend/evaluation/reports/sql-repair-evaluation-2026-06-11-093244.json`

| 指标 | v0.3 基线 | v0.4 基线 |
|---|---:|---:|
| 正常分析执行成功率 | 100% | 100% |
| 危险请求阻断率 | 87.5% | 100% |
| 安全预期命中率 | 96.9% | 100% |
| 平均 NL2SQL LLM 调用数 | 1.78 | 1.63 |
| 平均 NL2SQL Token | 1,889.28 | 1,712.81 |
| 平均 NL2SQL LLM 耗时 | 9,301 ms | 7,345.50 ms |
| Repair 端到端成功率 | 100% | 100% |

8 条危险请求中，4 条在 Intent Guard 提前终止，4 条继续由 SQL Guard 阻断。提前阻断请求不加载 Schema、不调用 Qwen、不访问数据库，因此安全能力提升的同时，平均模型调用、Token 和耗时也下降。

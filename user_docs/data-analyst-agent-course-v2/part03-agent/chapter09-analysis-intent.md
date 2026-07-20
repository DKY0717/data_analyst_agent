# 第9章 结构化分析意图

> 本章预计 1～2 小时。目标是把自然语言问题拆成可检查的业务槽位，而不是立即生成 SQL。默认练习使用规则与 Fake LLM，不产生外部费用。

## 9.1 学习目标

> 能解释 task type、指标、维度、过滤、时间粒度、排名、证据、置信度、缺失槽位和冲突；能手写 `AnalysisIntent`，并读懂规则与 LLM 的合并结果。

## 9.2 前置知识

> 需要理解业务问题与 `SELECT/GROUP BY/WHERE/ORDER BY/LIMIT` 的大致对应关系，并完成第8章最小 NL2SQL。

## 9.3 为什么需要这一模块

> 从问题直接跳到 SQL 会把“理解错了”和“SQL 写错了”混在一起。结构化 Intent 是可观测中间层：即使最终 SQL 失败，也能先判断系统是否正确识别了指标、维度与过滤条件。
>
> 规则解析擅长年份、Top-N、已登记别名等确定模式；LLM 擅长表达变化与隐含语义。双路解析不是投票，而是把可确定事实优先保留，并显式记录无法安全消解的冲突。

## 9.4 输入、输出与依赖

| 字段 | 示例 | 后续用途 |
|---|---|---|
| `task_types` | `aggregation`、`ranking` | 描述分析任务 |
| `metrics` | 销售额 | Grounding 到指标表达式 |
| `dimensions` | 地区 | Grounding 到分组字段 |
| `filters` | 年份等于 2024 | 映射到字段与 WHERE |
| `time_granularity` | month | 时间分组 |
| `ranking` | desc / 3 | ORDER BY 与 LIMIT |
| `missing_slots` | metric | 触发澄清证据 |
| `conflicts` | rule 与 LLM 不一致 | 降低置信度或澄清 |

> `IntentSlot` 只保存业务 concept、confidence 与 evidence，不在这一层绑定物理表列。这样“理解业务词”和“确认数据库实现”可以分别测试。

## 9.5 执行流程

```text
Question
  ├─ Rule Parser → deterministic slots
  └─ LLM Parser  → semantic slots
           ↓
       Merger
           ↓
AnalysisIntent + conflicts + overall_confidence
```

## 9.6 当前代码地图

| 模块 | 路径 | 关注符号 |
|---|---|---|
| 数据模型 | `backend/app/analysis_intent/models.py` | `AnalysisIntent` |
| 规则解析 | `backend/app/analysis_intent/rule_parser.py` | `AnalysisIntentRuleParser.parse` |
| LLM 解析 | `backend/app/analysis_intent/llm_parser.py` | `AnalysisIntentLLMParser.parse` |
| 合并器 | `backend/app/analysis_intent/merger.py` | `AnalysisIntentMerger.merge` |
| 图节点 | `backend/app/agents/graph.py` | `_parse_intent` |
| 用例 | `backend/evaluation/cases/intent_grounding_cases.yaml` | 固定评测输入 |

## 9.7 关键代码理解

### 9.7.1 规则先提供高确定性证据

> 规则解析器识别语义别名、年份过滤与排名，例如“最高的三个”可形成 `direction=desc, limit=3`。规则没有命中时应留下缺失信息，而不是编造槽位。

### 9.7.2 LLM 输出仍要进入模型契约

> LLM Parser 调统一客户端取得结构化数据，再构造 `AnalysisIntent`。模型说“地区”并不等于数据库一定存在 `region` 列；这只是待 Grounding 的候选。

### 9.7.3 Merger 如何处理冲突

```python
ranking = rule_intent.ranking or llm_intent.ranking
if conflicts:
    overall_confidence *= 0.8
```

> 同概念槽位按 rule→LLM 顺序去重，因此规则候选优先；两边指标或维度完全不重合时，冲突保留双方概念；ranking 或时间粒度不一致也进入 conflicts。系统不悄悄删除证据。

### 9.7.4 缺失槽位可被合并结果消除

> 两侧缺失项去重；如果合并后已经有 metric，就移除 `metric` 缺失。这样“规则没找到、LLM 找到了”的情况不会无条件澄清，但 LLM 候选仍需 Grounding。

## 9.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要，测试使用确定性替身。

```bash
pytest backend/tests/test_analysis_intent_integration.py backend/tests/test_intent_evaluator.py -q
```

> 手工拆解“2024 年销售额最高的三个地区”：metric=销售额、dimension=地区、filter=year 2024、ranking=desc/3。不要提前写成 `orders.total_amount`。

## 9.9 故障注入实验

> 输入“帮我分析一下”，预期缺少 metric，系统后续应请求澄清而不是强迫生成 SQL。再构造 rule=销售额、LLM=订单数的两个 Intent，观察 conflicts 与 overall_confidence 的变化。

## 9.10 调试路径与常见误判

> 调试顺序：原问题→规则 Intent→LLM Intent→合并 Intent→Grounding。规则命中不等于物理字段正确，LLM 高 confidence 也不是数据库事实；冲突不等于程序异常，而是风险证据。

## 9.11 独立编码练习

> 为“2024 年退款率最低的五个商品类别”手写完整 Intent JSON，并给每个槽位写 evidence。再写一个冲突 LLM 候选，预测合并结果。

## 9.12 测试或评测验证

> 至少验证年份、Top-N、规则/LLM互补、完全不重合冲突、缺失 metric 五类情况。Intent 评测只证明槽位，不证明 SQL 和结果正确。

## 9.13 面试复述题

> 1. 为什么需要规则与 LLM 双路解析？
>
> 2. 为什么 Intent 不直接保存数据库字段？
>
> 3. 冲突为什么要保留而不是选择置信度更高的一边？

## 9.14 掌握度检查与下一章

> 能把任意分析问题拆成槽位；能预测 merger；能说明 Intent 证据边界。完成后进入语义层与元数据目录。

# 第11章 Schema Grounding 与主动澄清

> 本章预计 1～2 小时，学习在 SQL 生成前把业务概念绑定到可解释的物理候选，并在风险过高时暂停。练习无需真实模型。

## 11.1 学习目标

> 能解释 GroundingCandidate、候选评分、维度覆盖、SchemaRoute、最短 JOIN 路径、澄清候选 ID、暂停与恢复。

## 11.2 前置知识

> 需要完成第9～10章，理解 Intent、语义定义、物理表列和 JOIN 图。

## 11.3 为什么需要这一模块

> Intent 中的“销售额”“地区”仍是业务词。Grounding 负责回答它们对应哪些表达式、表、列和连接边；澄清负责在缺少关键槽位或存在冲突时，把不确定性还给用户，而不是让模型猜。

## 11.4 输入、输出与依赖

| 输入 | 输出 |
|---|---|
| `AnalysisIntent` | metric/dimension groundings |
| 语义指标和维度 | 有稳定 ID、表达式、表列、score、evidence 的候选 |
| JOIN 配置 | `selected_tables`、`join_edges`、route confidence |
| 低置信/缺失/冲突 | `ClarificationRequest` 或继续 |

> Grounding 返回全部候选，但路由只使用每个概念得分最高的候选，避免低分覆盖候选污染必要表集合。

## 11.5 执行流程

```text
Intent → metric/dimension candidates
       → choose highest score for route
       → shortest paths in JOIN graph
       → clarification assessment
          ├─ pause + persist options
          └─ load physical schema
```

## 11.6 当前代码地图

| 内容 | 路径 | 关注点 |
|---|---|---|
| Grounding | `backend/app/agents/grounding.py` | 候选、覆盖、最短路 |
| 模型 | `backend/app/analysis_intent/models.py` | 候选与 route 契约 |
| 澄清 | `backend/app/agents/clarification.py` | 阈值、问题与选项 |
| 会话恢复 | `backend/app/agents/session_store.py` | pending clarification |
| 图决策 | `backend/app/agents/graph.py` | `_should_request_clarification` |

## 11.7 关键代码理解

### 11.7.1 指标候选和维度覆盖

> 默认指标表达式通常得分 1.0；存在适用维度覆盖时，默认候选降为 0.8，匹配当前维度的覆盖候选升为 1.0，未使用的覆盖候选为 0.5。评分是可解释排序规则，不是模型概率。

### 11.7.2 最小连通子图

> Grounder 对最高分候选涉及的表两两求最短路径，并合并字段级 JOIN 边。所有表连通时 route confidence 为 1.0；空集合或不可达时为 0.0。当前电商 JOIN 图近似树状，因此路径并集可解释。

```text
orders.customer_id = customers.customer_id
customers.region_id = regions.region_id
```

### 11.7.3 澄清并非所有低置信请求都会触发

> `ClarificationEngine` 的基础阈值是 0.5、最多两轮，但图层还做产品决策：当前实现只有带 `session_id` 的请求才进入主动澄清判断；明确 conflicts 会澄清；“帮我分析一下”等模糊标记且缺 metric 会澄清；已有上下文的省略式追问优先继承历史。

### 11.7.4 稳定恢复

> 待澄清内容保存原问题、clarification_id 与候选。用户用 candidate_id 或与候选完全匹配的文本恢复；候选被消费后删除。过期/错误 ID 返回 `clarification_expired`，不会继续下游调用。

## 11.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_schema_grounding_precision.py backend/tests/test_analysis_intent_integration.py -q
```

## 11.9 故障注入实验

> 使用带 session_id 的“帮我分析一下”，确认在 SQL 生成和数据库访问前返回候选；再用错误 clarification_id 恢复，确认稳定过期状态。实验后清理临时 SessionStore。

## 11.10 调试路径与常见误判

> 依次检查 Intent concept、语义查找、候选 score、source tables/columns、JOIN edge、route confidence、图层澄清条件。`ClarificationEngine.check()` 能生成请求，不代表图一定采用它；这是模块规则与产品路由的区别。

## 11.11 独立编码练习

> 为“按地区拆一下”分别设计无历史和有历史两种状态，预测是否澄清。再为两个不连通表画 route 失败证据。

## 11.12 测试或评测验证

> 覆盖默认候选、维度覆盖、最短路、不可达、候选稳定排序、过期 ID 与已消费候选。Grounding 命中仍不证明最终 SQL 有权限。

## 11.13 面试复述题

> 1. Grounding 与 Schema Loader 有什么区别？
>
> 2. 为什么澄清必须在 SQL 生成前？
>
> 3. 候选 ID 为什么比展示文案更适合恢复任务？

## 11.14 掌握度检查与下一章

> 能从 concept 追到表达式和 JOIN；能预测暂停/恢复条件；能说明当前只对带 session_id 请求澄清的边界。下一章进入 LangGraph。

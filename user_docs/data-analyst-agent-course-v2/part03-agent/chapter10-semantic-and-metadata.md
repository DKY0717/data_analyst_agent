# 第10章 语义层与元数据目录

> 本章预计 1～2 小时，学习把业务概念与物理 Schema 分开管理。练习只读取 YAML 和测试数据库。

## 10.1 学习目标

> 能解释指标口径、别名、默认表、时间字段、维度、JOIN 配置和 MetadataCatalog；能区分“别名命中”“候选生成”与“物理映射已验证”。

## 10.2 前置知识

> 需要掌握第3章八表关系、第5章物理 Schema 与第9章 Intent 槽位。

## 10.3 为什么需要这一模块

> `information_schema` 只告诉系统存在 `total_amount`、`paid_amount`、`refund_amount`，无法决定用户说“销售额”时采用哪个业务口径。语义层集中定义业务词，减少 Prompt 内散落口径和模型临场猜测。
>
> MetadataCatalog 将语义配置与当前物理 Schema 组合，提供候选与 JOIN 图。它是 Grounding 的检索基础，不是另一个 LLM。

## 10.4 输入、输出与依赖

| 来源 | 提供内容 | 不负责 |
|---|---|---|
| 物理 Schema | 表、列、类型、主外键 | 业务口径 |
| 语义 YAML | 指标/维度、表达式、别名、默认值、JOIN | 当前数据库是否真的匹配 |
| MetadataCatalog | 候选、表结构、join edges | 最终风险决策 |

> `SemanticLoader` 加载配置并支持按关键词查找；`MetadataCatalog.from_sources()` 把 Schema 与语义源组合，生成指标/维度候选和连通边。

## 10.5 执行流程

```text
ecommerce_metrics.yaml ─┐
                        ├→ SemanticLoader → MetadataCatalog
physical schema ────────┘          ↓
business concept → candidates + source tables/columns + join edges
```

## 10.6 当前代码地图

| 内容 | 路径 | 关注点 |
|---|---|---|
| 电商语义 | `backend/app/semantic/ecommerce_metrics.yaml` | 指标、维度、JOIN |
| 通用模板 | `backend/app/semantic/generic_template.yaml` | 非电商起点 |
| 加载器 | `backend/app/semantic/semantic_loader.py` | 查找与 Prompt 摘要 |
| 目录 | `backend/app/schema_context/metadata_catalog.py` | 候选与 join edges |
| 测试 | `backend/tests/test_semantic_loader.py` | 配置契约 |

## 10.7 关键代码理解

### 10.7.1 指标不是单纯列名

> 指标定义可能包含聚合表达式、默认表、别名和默认时间字段。例如订单数、销售额、客单价与退款率的分子/分母不同，必须把口径版本化并测试。

### 10.7.2 维度也有查询范围

> “地区”“省份”“城市”应是不同最小维度。相似地理词若都映射为同一候选，会让模型选错分组字段。维度配置应明确表与列。

### 10.7.3 JOIN 图来自两类证据

> MetadataCatalog 可从物理外键和语义 JOIN 配置建立边。候选涉及多表时，Grounder 在图上寻找连接路径。配置边不是越权许可证，最终 SQL 仍需 Guard 与 Permission。

### 10.7.4 通用模板的边界

> `generic_template.yaml` 可以帮助迁移到新领域，但不能自动创造业务口径。接入企业 Schema 时必须与业务方确认指标、粒度、时间和权限。

## 10.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py -q
```

> 选择“销售额”与“地区”，分别记录语义定义、候选表列和必要 JOIN。若只写出列名，说明还没有理解口径。

## 10.9 故障注入实验

> 在测试构造的内存配置中让两个维度共享同一别名，观察候选歧义；再拆成明确别名恢复。不要修改正式 YAML，也不要把测试配置提交为业务定义。

## 10.10 调试路径与常见误判

> 候选错误时按“关键词→YAML 别名→加载结果→物理 Schema→catalog 候选→JOIN edge”检查。别名命中不代表表达式有效；物理列存在也不代表业务口径正确；JOIN 可达不代表用户有权限。

## 10.11 独立编码练习

> 为“平均订单金额”写一份指标草案：名称、别名、表达式、默认表、默认时间字段、必要状态过滤与业务假设。只写草案，不直接修改生产 YAML。

## 10.12 测试或评测验证

> 为草案设计别名查找、表达式源列存在、默认时间字段存在、JOIN 可达四类测试。现有专项命令：

```bash
pytest backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py backend/tests/test_schema_grounding_precision.py -q
```

## 10.13 面试复述题

> 1. 语义层如何降低业务口径幻觉？
>
> 2. MetadataCatalog 和 SchemaLoader 有什么区别？
>
> 3. 为什么“候选可达”仍不能直接执行 SQL？

## 10.14 掌握度检查与下一章

> 能从业务词找到定义、物理候选和 JOIN 证据；能说出每层不负责什么。下一章进入 Grounding 与主动澄清。

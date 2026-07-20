# 第3章 SQL、DuckDB 与电商业务模型

> 本章预计 1～2 小时，建立 Agent 最终要操作的数据世界。

## 3.1 学习目标
> 能解释八张表关系，并手写包含 JOIN、过滤、聚合和排序的只读 SQL。

## 3.2 前置知识
> 需要了解 `SELECT`、`WHERE` 和简单聚合函数。

## 3.3 为什么需要这一模块
> 模型生成 SQL 是否正确，最终仍取决于表关系和业务口径。不了解一对多 JOIN，就无法识别重复聚合。

## 3.4 输入、输出与依赖
> SQL 输入表结构、筛选和指标表达式，输出列与结果行；项目演示使用 DuckDB，PostgreSQL 是可选生产适配。

## 3.5 执行流程
```text
customers → orders → order_items → products → categories
                    ↘ payments / refunds
```

## 3.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 建表 | `database/init.sql` |
| 种子数据 | `database/seed_data.py` |
| 设计说明 | `docs/database_design_md.md` |

## 3.7 关键代码理解
> 重点阅读主键、外键、金额字段和时间字段。分析销售额时要确认金额来自订单明细还是支付，分析退款时要确认分母和去重口径。

## 3.8 最小动手运行
```bash
python database/seed_data.py
pytest backend/tests/test_seed_data.py -q
```
> 命令不访问网络，但会重建项目约定的演示数据。

## 3.9 故障注入实验
> 在练习 SQL 中暂时去掉 JOIN 条件，观察行数或聚合值异常；不要修改正式种子数据。

## 3.10 调试路径与常见误判
> SQL 成功执行不等于业务正确。笛卡尔积、重复明细和错误分母都可能返回合法结果。

## 3.11 独立编码练习
> 写出“2024 年各商品类别销售额”的 SQL，并解释每个 JOIN 的必要性。

## 3.12 测试或评测验证
> 对照 `backend/evaluation/cases/golden_result_cases.yaml`，观察黄金结果如何约束列、排序和数值。

## 3.13 面试复述题
> 为什么结果正确性评测比“SQL 能执行”更严格？

## 3.14 掌握度检查与下一章
> 能从业务问题定位指标、维度、时间和必要表。下一章学习环境与调试。

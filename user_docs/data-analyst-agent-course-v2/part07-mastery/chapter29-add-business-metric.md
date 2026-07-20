# 第29章 实战一：新增业务指标
> 本章预计 1～2 小时，通过新增“净支付金额”练习一次跨层安全改造。
## 29.1 学习目标
> 能独立完成指标定义、语义映射、权限检查、提示上下文、评测用例和前端展示验证。
## 29.2 前置知识
> 已掌握电商 Schema、Intent、语义层、Grounding、权限与评测体系。
## 29.3 为什么需要这一模块
> Agent 项目的真实需求很少只改一个函数；业务指标会同时影响理解、生成、验证和产品解释。
## 29.4 输入、输出与依赖
> 输入是业务口径与允许访问的表列；输出是可被识别、正确落地、受权限约束且有评测证据的新指标。
## 29.5 执行流程
```text
define metric → map schema → parse/ground → generate/guard → evaluate → present
```
## 29.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 指标定义 | `backend/app/semantic/ecommerce_metrics.yaml` |
| 规则解析 | `backend/app/analysis_intent/rule_parser.py` |
| Grounding | `backend/app/agents/grounding.py` |
| 权限策略 | `backend/app/security/data_permissions.yaml` |
| 评测用例 | `backend/evaluation/cases/` |
## 29.7 关键代码理解
> 先写清口径再改代码。例如“净支付金额”必须明确退款如何扣除、空值如何处理、粒度和时间字段是什么，否则模型生成正确语法也无法保证业务正确。
## 29.8 最小动手运行
```bash
pytest backend/tests/test_semantic_loader.py backend/tests/test_schema_grounding_precision.py backend/tests/test_permission_execution_integration.py -q
```
## 29.9 故障注入实验
> 故意让规则解析器和语义 YAML 使用两个不同的指标名，观察合并或 Grounding 在何处失配。
## 29.10 调试路径与常见误判
> 按“口径—Intent—Grounding—SQL—结果—展示”逐层查；不要只看到 SQL 执行成功就认为指标完成。
## 29.11 独立编码练习
> 在独立分支实现一个自选业务指标，提交前写出受影响文件、风险和回滚方式。
## 29.12 测试或评测验证
> 至少覆盖同义问法、分组查询、权限受限角色、黄金结果和旧指标回归。
## 29.13 面试复述题
> 新增一个指标时，为什么要修改并验证多个层，而不是只改 Prompt？
## 29.14 掌握度检查与下一章
> 能独立列出完整改造面与验收证据。下一章进行端到端调试演练。

# 第25章 SQL Repair 与结果正确性评测
> 本章预计 1～2 小时，学习为什么 SQL 可执行仍不足以证明答案正确。
## 25.1 学习目标
> 能解释 Repair 成功率、结果比较和参考查询三种证据。
## 25.2 前置知识
> 熟悉 SQL 执行、错误分类、修复重试和 NL2SQL 评测。
## 25.3 为什么需要这一模块
> 修复后的 SQL 可能只是“不报错”，但聚合、过滤或连接语义仍然错误，因此必须比较结果。
## 25.4 输入、输出与依赖
> 输入是损坏 SQL、错误信息、黄金查询和数据库快照；输出是修复证据与结果等价判定。
## 25.5 执行流程
```text
broken SQL → repair → guarded execution → compare with reference result
```
## 25.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Repair 评测 | `backend/evaluation/repair_evaluator.py` |
| 参考查询 | `backend/evaluation/reference_query_runner.py` |
| 结果比较 | `backend/evaluation/result_comparator.py` |
| 正确性评测 | `backend/evaluation/result_correctness_evaluator.py` |
## 25.7 关键代码理解
> 结果比较需要明确列、行顺序、数值容差和空值规则；否则同义结果会误报，错误结果也可能被放过。
## 25.8 最小动手运行
```bash
pytest backend/tests/test_repair_evaluator.py backend/tests/test_result_correctness_evaluator.py -q
```
## 25.9 故障注入实验
> 把 `SUM` 改为 `COUNT` 并保持 SQL 可执行，观察结果正确性评测为何必须失败。
## 25.10 调试路径与常见误判
> Repair 通过只表示达成该用例契约；不要把执行成功率包装成业务准确率。
## 25.11 独立编码练习
> 为浮点聚合结果设计一个合理容差用例，并解释为何不能用字符串完全相等。
## 25.12 测试或评测验证
> 固定评测数据库，先验证参考查询，再比较候选结果，避免黄金答案自身不稳定。
## 25.13 面试复述题
> 一条 SQL 成功执行后，还需要哪些证据才能说答案正确？
## 25.14 掌握度检查与下一章
> 能区分可执行、已修复与结果正确。下一章学习长评测的分片与证据汇总。

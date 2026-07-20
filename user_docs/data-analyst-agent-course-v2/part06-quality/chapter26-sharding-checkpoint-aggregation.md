# 第26章 评测分片、Checkpoint 与严格汇总
> 本章预计 1～2 小时，学习真实模型长任务如何保留可审计证据。
## 26.1 学习目标
> 能解释确定性分片、原子 checkpoint 和 fail-closed 汇总。
## 26.2 前置知识
> 理解评测用例、CI 矩阵和进程中断风险。
## 26.3 为什么需要这一模块
> 长评测可能超时或被取消；如果只在最后写报告，已经完成的样例也会失去证据。
## 26.4 输入、输出与依赖
> 输入是固定用例列表、分片索引和总数；输出是逐分片 checkpoint 与通过身份校验的全集报告。
## 26.5 执行流程
```text
cases[index::count] → incremental atomic checkpoint → strict aggregator → full report
```
## 26.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 分片组件 | `backend/evaluation/shard_support.py` |
| 严格汇总 | `backend/evaluation/shard_report_aggregator.py` |
| 测试 | `backend/tests/test_shard_support.py` |
## 26.7 关键代码理解
> 分片先写临时文件再原子替换；汇总器验证分片编号、总数、SHA、用例覆盖、重复和完成状态，缺证据时拒绝生成正式全集报告。
## 26.8 最小动手运行
```bash
pytest backend/tests/test_shard_support.py backend/tests/test_shard_report_aggregator.py -q
```
## 26.9 故障注入实验
> 删除一个分片 checkpoint 或复制一个编号，确认汇总器明确报告缺失或重复，而不是计算残缺分数。
## 26.10 调试路径与常见误判
> Job 成功数量不等于用例覆盖完整；必须检查 checkpoint 身份和严格汇总结论。
## 26.11 独立编码练习
> 用 7 个虚拟用例和 3 个分片手算每个分片应得到的用例索引。
## 26.12 测试或评测验证
> 覆盖空 checkpoint、中断后部分结果、SHA 不匹配、缺片与重复片场景。
## 26.13 面试复述题
> 为什么严格汇总应该 fail closed，而不是对现有分片直接算平均分？
## 26.14 掌握度检查与下一章
> 能证明报告的完整性来源。下一章把这些证据接入 GitHub Actions 门禁。

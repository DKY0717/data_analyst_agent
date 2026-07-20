# 第28章 MiMo 真实评测超时事故复盘
> 本章预计 1～2 小时，用真实运行 `29634864907` 学习如何诚实分析不完整的模型证据。
## 28.1 学习目标
> 能区分功能失败、模型尾延迟、分片超时、证据不完整和质量门禁失败。
## 28.2 前置知识
> 已掌握分片 checkpoint、GitHub Actions 和严格质量门禁。
## 28.3 为什么需要这一模块
> Agent 工程能力不仅是写流程，还包括在供应商行为异常时保留证据、定位瓶颈并拒绝夸大结论。
## 28.4 输入、输出与依赖
> 输入是目标提交 `8dffc1d76c514c7efe1b6e642ea1880a81989109` 的 Job、日志和 Artifact；输出是脱敏根因分析与后续改进假设。
## 28.5 执行流程
```text
confirm SHA → inspect all shards → read failed logs → inspect artifacts → evaluate strict gate
```
## 28.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 真实模型工作流 | `.github/workflows/real-qwen-evaluation.yml` |
| LLM 重试 | `backend/app/services/llm_service.py` |
| 观测轨迹 | `backend/app/services/llm_observability.py` |
| 严格汇总 | `backend/evaluation/shard_report_aggregator.py` |
## 28.7 关键代码理解
> 本次 MiMo `mimo-v2.5-pro` 运行中，NL2SQL 13 个分片有 8 个成功，4、6、8、10、12 在 75 分钟步骤上限超时；Repair 3/3、结果正确性 5/5 成功。日志出现多次 reasoning 有值但 content 为空，触发重试并放大尾延迟。因为 NL2SQL 证据不完整，严格汇总和质量门禁失败，因此不能宣称真实模型全量通过。
## 28.8 最小动手运行
```bash
gh run view 29634864907 --json headSha,status,conclusion,jobs,url
```
## 28.9 故障注入实验
> 在本地用替身模拟“reasoning 非空、content 为空”，验证重试次数、观测字段和最终错误分类。
## 28.10 调试路径与常见误判
> 超时不自动等于 SQL 能力差，但也不能被解释为通过；只能陈述已有局部证据和缺失范围。
## 28.11 独立编码练习
> 提出三项可验证改进：单请求截止时间、空内容快速分类、按实际耗时重新分片，并为每项定义成功指标。
## 28.12 测试或评测验证
> 用 LLM Service 与观测性单测验证异常响应处理；任何工作流优化都必须重新产生完整 Artifact 后才能改变结论。
## 28.13 面试复述题
> 面对 8/13 NL2SQL 分片成功，你会如何向面试官准确描述项目状态？
## 28.14 掌握度检查与下一章
> 能给出不泄密、不甩锅、不夸大的事故复盘。下一部分开始独立改造和重建。

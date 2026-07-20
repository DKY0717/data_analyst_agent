# 第27章 GitHub Actions 与质量门禁
> 本章预计 1～2 小时，学习 CI 如何从运行测试升级为发布决策证据。
## 27.1 学习目标
> 能读懂普通 CI、真实模型矩阵、Artifact 汇总和阈值门禁。
## 27.2 前置知识
> 已理解测试金字塔、各类评测和严格分片汇总。
## 27.3 为什么需要这一模块
> 单个绿色 Job 只能证明局部步骤成功；质量门禁要确认所有必需证据完整且指标达到约定阈值。
## 27.4 输入、输出与依赖
> 输入是提交 SHA、Secrets、测试和评测 Artifact；输出是 Checks、Summary、报告与通过/失败结论。
## 27.5 执行流程
```text
preflight → shard matrices → artifact download → strict aggregation → quality gate
```
## 27.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 普通 CI | `.github/workflows/ci.yml` |
| 真实模型 CI | `.github/workflows/real-qwen-evaluation.yml` |
| 门禁实现 | `backend/evaluation/quality_gate.py` |
| 门禁测试 | `backend/tests/test_quality_gate.py` |
## 27.7 关键代码理解
> 工作流中的 `needs`、`if: always()` 和 Artifact 下载决定失败后还能否收集证据；门禁必须以报告内容为准，而不是仅看上游 Job 标签。
## 27.8 最小动手运行
```bash
pytest backend/tests/test_quality_gate.py backend/tests/test_report_writer.py -q
```
## 27.9 故障注入实验
> 给门禁一份缺少必需评测报告的输入，确认其失败并指出缺失证据。
## 27.10 调试路径与常见误判
> 先确认 head SHA，再看 Job、Step、Artifact、严格汇总和门禁；不要只截取某个绿色分片作为整体验收结论。
## 27.11 独立编码练习
> 为一个新指标写“报告缺失、字段缺失、低于阈值、通过”四种门禁用例。
## 27.12 测试或评测验证
> 本地验证门禁纯逻辑，远端只读检查实际工作流的 SHA、分片结果和汇总结论。
## 27.13 面试复述题
> 质量门禁与普通 pytest 通过有什么本质区别？
## 27.14 掌握度检查与下一章
> 能从提交追溯到最终证据。下一章复盘一次真实 MiMo 超时事故。

# 第7章 OpenAI-compatible LLM 客户端

> 本章预计 1～2 小时，优先使用 Mock 学习，不要求真实 API Key。

## 7.1 学习目标
> 能解释消息格式、结构化输出、超时、重试、空内容和可观测记录。

## 7.2 前置知识
> 需要理解 JSON、异步 HTTP 和异常处理。

## 7.3 为什么需要这一模块
> 外部模型具有网络、认证、限流、格式漂移和长尾延迟风险，不能让每个 Agent 节点自行处理这些细节。

## 7.4 输入、输出与依赖
> 输入是系统消息、用户消息和结构化任务；输出是解析后的对象或清洗后的异常；依赖 OpenAI-compatible HTTP endpoint。

## 7.5 执行流程
```text
Prompt → HTTP 请求 → 状态检查 → content/reasoning → JSON 解析 → 轨迹记录
```

## 7.6 当前代码地图
| 内容 | 路径 |
|---|---|
| LLM 服务 | `backend/app/services/llm_service.py` |
| Prompt | `backend/app/services/prompt_registry.py` |
| 测试 | `backend/tests/test_llm_service.py` |

## 7.7 关键代码理解
> 关注逻辑调用与 HTTP 尝试的区别、可重试异常分类、空 content 的处理，以及日志为何只能保存脱敏信息。

## 7.8 最小动手运行
```bash
pytest backend/tests/test_llm_service.py -q
```
> 该测试使用确定性响应，不访问外部模型。

## 7.9 故障注入实验
> 使用 Mock 依次返回超时、429、非法 JSON 和空 content，观察重试次数与最终错误类型。

## 7.10 调试路径与常见误判
> reasoning 非空不代表 content 可用；API Key 缺失、模型拒绝和 JSON 解析失败也不能使用同一个错误结论。

## 7.11 独立编码练习
> 为练习客户端设计一个最多两次尝试的结构化调用接口，并记录逻辑调用耗时。

## 7.12 测试或评测验证
> 从测试中找出成功、可重试失败和不可重试失败各一个用例，解释预期。

## 7.13 面试复述题
> 为什么统一 LLM 边界比在每个 Agent 节点直接调用 HTTP 更可靠？

## 7.14 掌握度检查与下一章
> 能区分模型业务输出与 HTTP 传输行为。下一章把 Schema、LLM 和数据库组成最小闭环。

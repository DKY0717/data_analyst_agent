# 第6章 FastAPI 请求与异常边界

> 本章预计 1～2 小时，理解 HTTP 如何进入 Python 业务逻辑。

## 6.1 学习目标
> 能解释路由、依赖、请求校验、响应模型和统一异常处理。

## 6.2 前置知识
> 需要理解 HTTP 方法、JSON 和第2章的 Pydantic 模型。

## 6.3 为什么需要这一模块
> API 是不可信外部输入进入系统的第一道契约边界，也是前端、认证和 Agent 的连接点。

## 6.4 输入、输出与依赖
> 输入是 HTTP 请求、问题和身份；输出是结构化 QueryResponse 或稳定错误；依赖 FastAPI、认证和 AgentGraph。

## 6.5 执行流程
```text
HTTP → 路由 → 依赖与校验 → Agent → 响应模型 → HTTP
```

## 6.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 应用 | `backend/app/main.py` |
| 查询路由 | `backend/app/api/query.py` |
| 模型 | `backend/app/models/schemas.py` |

## 6.7 关键代码理解
> 重点区分 HTTP 状态、业务状态和 Agent 状态。澄清、阻断和失败不应该都被压缩成一个模糊字符串。

## 6.8 最小动手运行
```bash
pytest backend/tests/test_query_api.py -q
```

## 6.9 故障注入实验
> 向测试客户端发送空问题和非法字段，观察校验发生在 Agent 调用之前。

## 6.10 调试路径与常见误判
> 200 响应不一定代表查询成功，可能是需要澄清；500 也不应暴露内部堆栈或 Secret。

## 6.11 独立编码练习
> 为一个只读版本信息接口设计请求、响应和测试，不接入 Agent。

## 6.12 测试或评测验证
> 对比 API 测试中的 Mock Agent 与真实 Agent 测试，解释各自边界。

## 6.13 面试复述题
> 为什么 API 响应要保留 `blocked`、`clarification_required` 和 `failed` 的区别？

## 6.14 掌握度检查与下一章
> 能从 HTTP 请求定位到业务调用和错误转换。下一章进入 LLM 客户端。

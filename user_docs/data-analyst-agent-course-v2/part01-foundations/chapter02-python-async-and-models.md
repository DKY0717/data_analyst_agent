# 第2章 Python、异步与类型模型

> 本章预计 1～2 小时，把 Python 基础连接到项目真实实现。

## 2.1 学习目标
> 能读懂模块导入、类型标注、Pydantic 模型、`async`/`await` 和 FastAPI 依赖函数。

## 2.2 前置知识
> 需要会定义函数、类、列表和字典，不要求掌握高级并发。

## 2.3 为什么需要这一模块
> Agent 同时包含异步 LLM 调用、数据库操作和结构化状态；不了解类型与异步会把“返回协程”和“返回结果”混为一谈。

## 2.4 输入、输出与依赖
> Pydantic 模型把外部 JSON 转成受约束的 Python 对象；异步函数把网络等待交还事件循环；依赖函数向路由提供身份和服务对象。

## 2.5 执行流程
```text
JSON 请求 → Pydantic 校验 → async 路由 → await Agent → Pydantic 响应
```

## 2.6 当前代码地图
| 概念 | 路径 |
|---|---|
| 请求响应模型 | `backend/app/models/schemas.py` |
| 配置模型 | `backend/app/config.py` |
| 异步入口 | `backend/app/api/query.py` |

## 2.7 关键代码理解
> 阅读模型时关注必填字段、默认值和 `Field(default_factory=...)`；阅读异步函数时关注每个 `await` 对应的是网络、工作流还是其他协程。

## 2.8 最小动手运行
```bash
python -c "from backend.app.models.schemas import QueryRequest; print(QueryRequest(question='统计销售额'))"
```
> 该命令无需网络；如果导入路径受当前目录影响，使用 pytest 的项目环境验证。

## 2.9 故障注入实验
> 构造缺少 `question` 的请求模型，观察校验错误结构，再恢复合法输入。

## 2.10 调试路径与常见误判
> `async` 不等于自动并行；只有遇到 `await` 且底层操作可异步等待时，事件循环才能处理其他任务。

## 2.11 独立编码练习
> 定义一个只包含问题、状态和可选 SQL 的练习模型，并为非法空问题设计校验预期。

## 2.12 测试或评测验证
```bash
pytest backend/tests/test_query_api.py -q
```

## 2.13 面试复述题
> Pydantic 模型为什么不仅是类型提示，还属于 API 安全和契约的一部分？

## 2.14 掌握度检查与下一章
> 能解释同步函数、协程、模型实例和 JSON 的差别。下一章进入 SQL 和业务表。

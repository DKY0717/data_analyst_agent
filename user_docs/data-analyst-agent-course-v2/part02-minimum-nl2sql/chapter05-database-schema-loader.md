# 第5章 数据库连接与 Schema Loader

> 本章预计 1～2 小时，学习程序如何认识数据库。

## 5.1 学习目标
> 能解释连接生命周期、Schema 元数据来源和格式化结果。

## 5.2 前置知识
> 需要掌握第3章的表、列和主外键概念。

## 5.3 为什么需要这一模块
> LLM 不应凭空猜测表列。Schema Loader 把数据库事实转换成可供后续 Grounding 和 SQL 生成使用的结构。

## 5.4 输入、输出与依赖
> 输入是数据库连接；输出是表、列、类型等 Schema 信息；依赖 `information_schema` 和项目连接配置。

## 5.5 执行流程
```text
Settings → Connection → information_schema → SchemaLoader → SchemaContext
```

## 5.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 连接 | `backend/app/db/connection.py` |
| 加载 | `backend/app/db/schema_loader.py` |
| 测试 | `backend/tests/test_schema_loader.py` |

## 5.7 关键代码理解
> 关注连接由谁创建和关闭、不同数据库方言如何分支、测试为何使用隔离数据库。

## 5.8 最小动手运行
```bash
pytest backend/tests/test_schema_loader.py -q
```

## 5.9 故障注入实验
> 在独立测试配置中指向不存在的数据库路径，观察连接或 readiness 错误，再恢复配置。

## 5.10 调试路径与常见误判
> Schema 为空可能是数据库未初始化、连接目标错误或权限不足，不应立即归因于 Prompt。

## 5.11 独立编码练习
> 写一个只打印表名和列名的只读练习函数，并说明它不应返回样本数据的原因。

## 5.12 测试或评测验证
> 阅读测试 fixture，解释为什么测试库不能共享本地业务库状态。

## 5.13 面试复述题
> Schema Loader 和业务语义层解决的是同一个问题吗？

## 5.14 掌握度检查与下一章
> 能说明 Schema 的来源、结构和失败点。下一章把这些能力暴露为 FastAPI 接口。

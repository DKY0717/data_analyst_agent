# 第5章 数据库连接与 Schema Loader

> 本章预计 1～2 小时，学习程序如何从真实数据库取得物理结构。全部练习可使用隔离数据库，不需要网络或 LLM。

## 5.1 学习目标
> 能解释连接生命周期、双后端差异、`information_schema`、约束解析和 `get_full_schema()` 的结构；能定位 Schema 为空与 Schema 加载异常。

## 5.2 前置知识
> 需要掌握第3章的表、列和主外键概念。

## 5.3 为什么需要这一模块
> LLM 不应凭空猜测表列。Schema Loader 把数据库事实转换为机器可读结构，约束 SQL 生成可使用的表和列。它只说明“数据库里有什么”，不说明“销售额如何计算”；后者属于语义层。

## 5.4 输入、输出与依赖
| 输入 | 输出 | 失败形式 |
|---|---|---|
| 数据库后端与连接 | 表名列表 | `SchemaLoadError` |
| 表名 | 列名、类型、nullable、主键、外键 | `SchemaLoadError` |
| 全部表 | `{"tables": {table_name: table_schema}}` | 统一脱敏错误 |

> 生产默认使用全局 `db_connection`，测试与确定性评测可向 `SchemaLoader(db=...)` 注入隔离连接。动态属性避免测试替换被构造时机锁死。

## 5.5 执行流程
```text
Settings → detect backend → get_session()
  → information_schema tables/columns
  → DuckDB/PostgreSQL constraint branch
  → {tables: {...}}
```

## 5.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 连接 | `backend/app/db/connection.py` |
| 加载 | `backend/app/db/schema_loader.py` |
| 格式化 | `backend/app/utils/schema_formatter.py` |
| 测试 | `backend/tests/test_schema_loader.py` |

## 5.7 关键代码理解
### 5.7.1 会话生命周期

> `get_session()` 由上下文管理器负责提交、回滚和关闭。调用方使用 `with`，异常离开时也能清理资源。不要在 Loader 中保存一个永久游标。

### 5.7.2 双后端适配

> DuckDB 使用 `main` schema 与 `?` 占位符；PostgreSQL 使用 `public` 与 `%s`。列信息来自 `information_schema.columns`，约束则分别走 PostgreSQL 信息表和 DuckDB 的 `duckdb_constraints()`。

```python
return {
    "table_name": table_name,
    "columns": [{"name": ..., "type": ..., "nullable": ...}],
    "primary_keys": primary_keys,
    "foreign_keys": foreign_keys,
}
```

> 表名作为参数传入列查询，不能把外部输入直接拼进 SQL。固定 schema 名来自后端分支，不来自用户请求。

### 5.7.3 错误脱敏

> Loader 在内部日志记录异常类型，对外抛出统一 `SchemaLoadError`，保留原异常链用于调试但不泄露连接细节。

## 5.8 最小动手运行
```bash
pytest backend/tests/test_schema_loader.py -q
```

> 工作目录：项目根目录。测试使用隔离连接，不访问真实模型，也不会读取生产数据库。

## 5.9 故障注入实验
> 使用临时目录构造一个空 DuckDB，调用 `get_full_schema()` 并观察空表集合；再执行 `database/init.sql` 后重试。不要改项目正式数据库路径。

## 5.10 调试路径与常见误判
> Schema 为空时依次检查：实际绝对连接目标、backend、schema 名、表是否初始化、当前身份是否能读元数据。表存在但外键为空时再检查后端约束查询与 DDL，不要先改 Prompt。

## 5.11 独立编码练习
> 写一个接收 `SchemaLoader` 的函数，只返回排序后的 `table.column:type`。通过依赖注入测试它，不读取样本行；Schema 与样本数据承担不同隐私风险和 Prompt 体积。

## 5.12 测试或评测验证
> 阅读测试 fixture，解释为什么临时数据库保证可重复、不会依赖个人本地状态，也不会被测试破坏。再运行：

```bash
pytest backend/tests/test_schema_loader.py backend/tests/test_schema_grounding_precision.py -q
```

## 5.13 面试复述题
> 1. Schema Loader 和业务语义层分别回答什么？
>
> 2. DuckDB 与 PostgreSQL 的元数据读取为什么需要分支？
>
> 3. 为什么测试要注入数据库而不是修改全局连接？

## 5.14 掌握度检查与下一章
> 能手写 `get_full_schema()` 的结果形状；说出两种后端的 schema 名和占位符；按证据定位空 Schema。完成后进入 FastAPI 边界。

# 第四章 初始化数据库与加载 Schema

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 4.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 说明应用为什么不能只依赖一份手写数据库说明；
> 2. 解释 `DatabaseConnection` 如何在 DuckDB 与 PostgreSQL 之间选择；
> 3. 解释 `information_schema`、主键和外键元数据的作用；
> 4. 读懂 `SchemaLoader.get_full_schema()` 返回的数据结构；
> 5. 说明物理 Schema 如何被格式化成大模型可以阅读的文本；
> 6. 使用隔离测试库验证 Schema 加载没有依赖开发者本机的数据库。

## 4.2 问题场景

> 第三章里我们通过 `init.sql` 知道了八张表，但运行中的数据库可能来自一个全新的 Docker 数据卷，也可能来自 PostgreSQL。SQL 生成器不能假设“我记得数据库长什么样”，它需要在请求时读取真实结构。
>
> 因此，本章要建立一条边界：数据库连接模块负责“如何连接”，Schema Loader 负责“数据库里有什么”，格式化工具负责“如何把结构交给下游模块”。三者职责不同，后续替换数据库后也不会把连接细节散落到 Agent 代码中。

## 4.3 数据库连接和会话生命周期

### 4.3.1 根据配置选择后端

> `backend/app/db/connection.py` 中的 `detect_backend()` 会先读取 `DATABASE_URL`。如果 URL 以 `postgresql://` 或 `postgres://` 开头，就选择 PostgreSQL；否则默认选择 DuckDB。`DATABASE_BACKEND` 显式配置时优先级更高。

```python
def detect_backend() -> str:
    url = settings.DATABASE_URL
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return "postgresql"
    return "duckdb"
```

> 这里的“自动选择”只决定连接方式，不代表两种数据库的所有 SQL 行为完全相同。项目仍然需要在查询、Schema 元数据和占位符上处理方言差异。

### 4.3.2 使用上下文管理器关闭连接

```python
@contextmanager
def get_session(self):
    conn = self.get_connection()
    try:
        yield conn
        if self.backend == "postgresql":
            conn.commit()
    except Exception as e:
        if self.backend == "postgresql":
            conn.rollback()
        raise DatabaseError(f"数据库会话错误: {e}")
    finally:
        conn.close()
```

> `with db_connection.get_session() as conn:` 是一个资源边界。正常结束时 PostgreSQL 提交事务，异常时回滚，最终无论成功还是失败都关闭连接。DuckDB 读取路径没有显式提交逻辑，但同样会关闭连接。
>
> 初学者常见误解是“连接对象可以全局复用，所以不需要关闭”。在 Web 服务中，请求会并发到达；不关闭连接会造成资源泄漏或锁竞争。这里的全局对象是连接管理器，不是一个永远打开的数据库连接。

## 4.4 为什么读取 information_schema

> `information_schema` 是数据库提供的元数据视图。应用通过它查询表名、列名、类型和可空性，而不是解析 `init.sql` 文件。这样做的好处是：当数据库由迁移或外部系统创建时，程序仍然能够观察实际结构。

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'main'
ORDER BY table_name;
```

> DuckDB 使用 `main` Schema，PostgreSQL 使用 `public` Schema；`SchemaLoader` 通过 `_schema_name` 属性统一这两个差异。列查询在 PostgreSQL 使用 `%s` 占位符，在 DuckDB 使用 `?` 占位符，这也是 `_placeholder` 属性存在的原因。

## 4.5 SchemaLoader 的输出

### 4.5.1 获取表名和单表结构

> `get_tables()` 返回排序后的表名列表。`get_table_schema(table_name)` 则返回一个字典，包含表名、字段、主键和外键。下游模块不需要知道数据库游标，只接收普通 Python 数据。

```python
{
    "table_name": "orders",
    "columns": [
        {"name": "order_id", "type": "INTEGER", "nullable": False},
        {"name": "customer_id", "type": "INTEGER", "nullable": True}
    ],
    "primary_keys": ["order_id"],
    "foreign_keys": [
        {
            "column": "customer_id",
            "referenced_table": "customers",
            "referenced_column": "customer_id"
        }
    ]
}
```

### 4.5.2 处理 DuckDB 约束信息

> PostgreSQL 可以直接从 `information_schema.table_constraints` 查询主键和外键；DuckDB 的约束信息由 `duckdb_constraints()` 提供。`_parse_constraints()` 从 DuckDB 的约束文本中提取引用表和引用列，最后把两种数据库整理成相同的输出结构。

> 这一步体现了一个重要的适配层思想：业务代码应该依赖稳定的数据结构，而不是依赖每个数据库的内部元数据格式。

### 4.5.3 加载完整 Schema

```python
def get_full_schema(self) -> Dict[str, Any]:
    tables = self.get_tables()
    schema = {}
    for table in tables:
        schema[table] = self.get_table_schema(table)
    return {"tables": schema}
```

> `get_full_schema()` 先获取表清单，再逐表加载结构，最终返回 `{"tables": {...}}`。这个结构会被 SQL Generator、Schema API 和测试共同使用。

## 4.6 从物理结构到 Prompt 文本

> 大模型不能直接理解 Python 字典的业务含义，因此 `format_physical_schema()` 把 Schema 变成稳定的文本格式。它保留表名、主键、字段名、字段类型和 NULL 约束，避免下游 Prompt 只看到一堆未经解释的 JSON。

```text
表名: orders
  主键: order_id
  字段:
    - order_id (INTEGER, NOT NULL)
    - customer_id (INTEGER, NULLABLE)
    - order_date (DATE, NULLABLE)
```

> 这里暂时只描述物理结构，不负责解释“销售额”这类业务词。业务口径由后续语义层提供。本章要建立的是物理事实边界：数据库里真实存在什么表和字段。

## 4.7 Docker 演示库的自动自举

> `demo_bootstrap.py` 只服务 DuckDB 演示场景。容器第一次启动时，它会检查八张业务表是否都存在且 `orders` 有数据；如果没有，就先执行 `database/init.sql`，再调用现有的 `seed_data.py`。如果数据卷已经初始化，则跳过写入，避免容器重启覆盖数据。

```python
if _has_seeded_business_data(connection):
    return "already_initialized"

connection.execute(init_sql_path.read_text(encoding="utf-8"))
seed_module = _load_seed_module(seed_path)
seed_module.seed_database(connection=connection, verbose=verbose)
```

> “已存在就跳过”不是简单的优化，而是持久化数据卷的安全条件。教程中的演示数据可以重建，但用户在运行中的数据不应该因为一次容器重启被覆盖。

## 4.8 执行流程

```text
应用启动
  ↓
读取 DATABASE_BACKEND / DATABASE_URL
  ↓
选择 DuckDB 或 PostgreSQL 连接方式
  ↓
SchemaLoader 查询 information_schema
  ↓
按数据库方言读取主键和外键
  ↓
返回统一的 SchemaContext
  ↓
format_physical_schema 转为 Prompt 文本
```

### 4.8.1 v1.7 的数据库生命周期边界

> 当前版本不再把“两个数据库都能运行”混同为“同一套迁移脚本适用于两个方言”。PostgreSQL 是生产结构，由 `backend/alembic/` 管理；DuckDB 是本地演示和确定性评测数据库，由 `database/init.sql` 与固定种子脚本重建。Alembic 环境会显式拒绝 DuckDB，避免迁移证据不足时静默误报成功。

```bash
# 仅在 PostgreSQL 环境执行迁移往返
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
python -m alembic -c backend/alembic.ini upgrade head
```

> 学习时先观察 `20260711_0001_initial_schema.py` 如何覆盖八张业务表，再运行 `backend/tests/test_migrations.py`。DuckDB 仍使用本章前面的初始化脚本，不要对它执行 PostgreSQL Alembic 命令。

## 4.9 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/db/connection.py` | 连接和会话生命周期 | 后端选择、提交、回滚、关闭 |
| `backend/app/db/schema_loader.py` | 读取表和约束 | `information_schema`、方言适配 |
| `backend/app/utils/schema_formatter.py` | 格式化物理 Schema | 稳定文本输出 |
| `backend/app/db/demo_bootstrap.py` | Docker 演示库自举 | 首次初始化与幂等判断 |
| `backend/alembic/versions/20260711_0001_initial_schema.py` | PostgreSQL 初始迁移 | 生产结构和可回滚边界 |
| `backend/tests/test_schema_loader.py` | Schema 行为测试 | 隔离连接、表结构和约束 |
| `backend/tests/test_migrations.py` | 迁移契约测试 | 单 revision、八张表和 DuckDB 边界 |

## 4.10 动手验证

> 先在项目根目录执行以下命令。它只验证 Schema Loader 的确定性行为，不需要真实 LLM。

```bash
pytest backend/tests/test_schema_loader.py -q
pytest backend/tests/test_migrations.py -q
```

> 预期结果是该测试文件全部通过。若出现数据库文件被占用，先确认没有并行运行多个会修改同一测试数据库的 pytest 进程，再串行重试。

> 也可以直接请求 Schema API。先启动后端，再在另一个终端执行：

```bash
curl http://127.0.0.1:8000/api/schema
```

> 返回 JSON 中应该能看到 `tables` 字段以及 `orders`、`products` 等业务表。该请求不调用大模型。

## 4.11 常见错误

### 数据库文件不存在

> `DatabaseError` 或“无法打开 database.duckdb”通常说明数据目录尚未创建，或者当前工作目录与配置中的 `BASE_DIR` 不一致。先确认 `backend/app/config.py` 计算出的 `DATA_DIR`，再运行数据库初始化或启动应用生命周期。

### 表存在但 Schema 为空

> 这通常不是 LLM 问题，而是连接到了错误的数据库文件、错误的 PostgreSQL 数据库，或者初始化脚本没有执行。先用 `/api/schema` 和 `information_schema.tables` 检查实际连接目标。

### PostgreSQL 占位符错误

> PostgreSQL 使用 `%s`，DuckDB 使用 `?`。不要把一种驱动的占位符硬编码到所有路径；应沿用 `SchemaLoader._placeholder` 的方言判断。

## 4.12 本章小结

> 本章建立了三个理解层次：连接管理器负责连接生命周期，Schema Loader 负责读取真实数据库元数据，格式化器负责把物理结构转换成下游可读文本。后续 SQL 生成器可以使用这些事实，但仍然需要知道业务指标的计算口径；这正是下一部分逐步加入的能力。

## 4.13 练习

1. 在测试库中新增一张只读测试表，观察 `get_tables()` 是否能发现它。
2. 为 `format_physical_schema()` 增加一个包含复合主键的最小输入，并说明输出是否符合预期。
3. 追踪 `/api/schema` 从路由到 `SchemaLoader.get_full_schema()` 的调用路径。
4. 删除测试数据库后重新启动应用，记录演示库自举前后八张表的变化。

## 4.14 下一章衔接

> 本章的输出是“程序知道数据库里有什么”。下一章会把这些能力放进 FastAPI 应用：定义 HTTP 契约、注册路由、处理应用启动和健康检查，让外部客户端可以稳定访问它们。

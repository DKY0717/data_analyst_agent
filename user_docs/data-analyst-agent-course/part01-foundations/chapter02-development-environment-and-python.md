# 第二章 开发环境与必备 Python 基础

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 2.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释 Python、虚拟环境、pip、Node.js 和 npm 在项目中的作用；
> 2. 正确安装后端和前端依赖；
> 3. 理解 Python 模块、导入、类型标注、同步与异步的最小知识；
> 4. 使用 `.env` 配置数据库、LLM、SQL 和认证边界；
> 5. 独立判断工作目录、依赖、端口和环境变量类错误。

## 2.2 问题场景

> 同一份代码在作者电脑上可以运行，在另一台电脑上却可能失败。常见原因包括 Python 版本不同、依赖未安装、命令在错误目录执行、环境变量没有加载、Node.js 缺失或端口已经被占用。
>
> 开发环境不是项目外部的杂事。它决定程序能否找到模块、连接哪个数据库、调用哪个模型、是否开启沙箱，以及前后端能否互相通信。

## 2.3 运行环境由哪些部分组成

| 组件 | 作用 | 项目中的证据 |
|---|---|---|
| Python | 运行 FastAPI、LangGraph、SQL Guard 和评测代码 | `backend/`、`database/`、`scripts/` |
| 虚拟环境 | 隔离项目依赖，避免不同项目版本冲突 | 由开发者本地创建 |
| pip | 根据 requirements 安装 Python 包 | `backend/requirements.txt` |
| Node.js | 运行 Vite、Vue 测试和前端构建 | `frontend/package.json` |
| npm | 安装前端依赖并执行 scripts | `frontend/package-lock.json` |
| DuckDB | 保存本地演示数据 | `data/database.duckdb` |
| 环境变量 | 保存模型地址、密钥、数据库和安全配置 | `.env.example`、`backend/app/config.py` |
| Git | 跟踪代码和文档版本 | `.git/` |

## 2.4 Python 模块与工作目录

### 2.4.1 文件、模块和包

> 一个 `.py` 文件通常可以看作一个模块。包含 Python 模块的目录可以组成包。项目中的 `backend/app/` 是核心应用包，`backend/app/security/sql_guard.py` 对应 `app.security.sql_guard` 模块。

```python
from app.config import settings
from app.api import health, schema, query, auth_router
```

> 这两个导入成立的前提是 Python 能在模块搜索路径中找到 `backend/app`。因此后端常用命令先进入 `backend`：

```bash
cd backend
uvicorn app.main:app --reload
```

> `app.main:app` 的第一个 `app` 是包，`main` 是模块，冒号后面的 `app` 是 FastAPI 对象。

### 2.4.2 为什么错误目录会导致导入失败

> 如果在项目根目录直接运行 `python -c "from app.main import app"`，Python 默认不会把 `backend` 当作顶层搜索目录，因此可能找不到 `app`。进入 `backend` 后，当前目录加入搜索路径，导入才能成立。

## 2.5 类型标注和数据边界

### 2.5.1 类型标注

```python
def _get_int(env_key: str, default: int) -> int:
    val = os.getenv(env_key, str(default))
    try:
        return int(val)
    except ValueError:
        raise ValueError(
            f"Environment variable {env_key} must be an integer, got: {val}"
        )
```

> `env_key: str` 表示参数预期是字符串，`default: int` 表示默认值预期是整数，`-> int` 表示函数返回整数。Python 类型标注主要帮助阅读、编辑器检查和静态分析，本身不会自动拒绝所有错误类型。
>
> 这段配置代码主动执行 `int(val)`，才真正把字符串环境变量转换为整数；转换失败时抛出带变量名的异常，避免系统悄悄使用错误配置。

### 2.5.2 Pydantic

> FastAPI 使用 Pydantic 模型定义请求和响应。Pydantic 会在 HTTP 边界把 JSON 数据校验为明确类型，并在输入不合法时返回结构化错误。后续第五章会结合查询接口完整讲解。

### 2.5.3 TypedDict

> LangGraph 的 `AgentState` 使用 `TypedDict` 描述共享字典中应该存在的字段。它保留普通字典的使用方式，同时让编辑器和开发者知道节点可以读取和写入哪些键。

```python
class AgentState(TypedDict):
    question: str
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    execution_success: bool
    retry_count: int
    answer: Optional[str]
```

## 2.6 同步、异步与 `async/await`

### 2.6.1 同步函数

```python
def ensure_directories():
    settings.DATA_DIR.mkdir(exist_ok=True)
    settings.LOG_DIR.mkdir(exist_ok=True)
```

> 同步函数从第一行执行到返回为止。创建目录是很短的本地操作，使用普通函数即可。

### 2.6.2 异步函数

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    init_tracing()
    logger.info("Data Analyst Agent API 启动")
    yield
    logger.info("Data Analyst Agent API 关闭")
```

> `async def` 定义协程函数。异步适合等待网络、数据库或队列等 I/O，不代表代码自动并行，也不意味着所有函数都应该改成异步。
>
> `lifespan` 在 `yield` 之前执行启动逻辑，在应用关闭后执行清理逻辑。FastAPI 负责等待这个异步上下文。

### 2.6.3 `await`

> 调用异步函数通常需要 `await`。当程序等待 LLM HTTP 响应时，事件循环可以处理其他请求；如果在异步函数中使用长时间阻塞操作，整个事件循环仍可能被卡住。

## 2.7 创建 Python 虚拟环境

### 2.7.1 Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

### 2.7.2 macOS 或 Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

> 激活虚拟环境后，`python` 和 `pip` 应该指向 `.venv`。如果安装包时没有激活环境，包可能被装进系统 Python 或另一个 Conda 环境，运行项目时仍然提示缺少依赖。

### 2.7.3 后端关键依赖

| 包 | 作用 |
|---|---|
| `fastapi`、`uvicorn` | HTTP 应用和开发服务器 |
| `pydantic`、`python-dotenv` | 数据校验和环境变量 |
| `duckdb`、`psycopg2-binary` | DuckDB 和 PostgreSQL 连接 |
| `httpx` | 异步调用 OpenAI-compatible LLM |
| `sqlglot` | SQL AST 解析和改写 |
| `langgraph` | Agent 状态图 |
| `pytest`、`pytest-asyncio` | 后端自动化测试 |
| `slowapi`、`PyJWT` | 限流和身份认证 |
| `opentelemetry-*` | 调用链和可观测性 |

## 2.8 安装前端环境

```bash
cd frontend
npm install
npm run dev
```

> `npm install` 根据 `package.json` 和 `package-lock.json` 安装依赖。`npm run dev` 实际执行 `vite --host 0.0.0.0`，启动开发服务器。

| 前端依赖 | 作用 |
|---|---|
| Vue 3 | 组件和响应式界面 |
| Vite | 开发服务器和生产构建 |
| Element Plus | UI 组件 |
| Pinia | 查询和认证状态管理 |
| Axios | HTTP 请求 |
| ECharts | 数据图表 |
| Vitest | 前端单元测试 |
| Playwright | 浏览器端到端测试 |

## 2.9 配置 `.env`

### 2.9.1 从示例文件创建本地配置

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

> `.env.example` 可以提交，因为它只包含示例值和安全默认；`.env` 可能包含真实 API Key，必须保持在 Git 忽略列表中。

### 2.9.2 LLM 配置

```text
QWEN_API_KEY=your_api_key_here
QWEN_API_URL=https://token-plan-cn.xiaomimimo.com/v1/chat/completions
QWEN_MODEL=mimo-v2.5-pro
```

> `QWEN_*` 是项目历史沿用的变量名，并不表示只能调用 Qwen。当前默认地址和模型是 MiMo，只要服务遵循项目使用的 OpenAI-compatible Chat Completions 协议，也可以切换到其他兼容端点。

### 2.9.3 数据库配置

```text
DATABASE_URL=duckdb:///./data/database.duckdb
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/data_analyst_agent
```

> 初学阶段使用 DuckDB。它是嵌入式数据库，不需要单独启动数据库服务器。生产或扩展学习可以切换 PostgreSQL，但 SQL 生成的默认教学方言仍是 DuckDB。

### 2.9.4 SQL 安全配置

```text
SQL_TIMEOUT=30
SQL_MAX_ROWS=1000
SQL_MAX_RETRIES=3
SANDBOX_MODE=true
```

> 这些变量限制执行时间、最大返回行数和修复次数。`SANDBOX_MODE=true` 表示默认使用子进程隔离执行，超时后父进程可以终止工作进程。学习时不要为了绕过错误直接关闭 Guard 或沙箱。

### 2.9.5 认证配置

```text
# JWT_SECRET=your-jwt-secret-key-here
# API_KEYS=sk-key1,sk-key2,sk-key3
# AUTH_DEMO_ENABLED=false
```

> 项目允许本地未配置认证时自动放行，便于初次运行；这不代表生产环境可以保持匿名访问。演示登录也必须显式开启，并且只用于本地受控演示。

## 2.10 Settings 如何读取环境变量

```python
class Settings:
    APP_PORT: int = _get_int("APP_PORT", 8000)
    DEBUG: bool = _get_bool("DEBUG", False)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "duckdb:///./data/database.duckdb",
    )
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    SQL_MAX_ROWS: int = _get_int("SQL_MAX_ROWS", 1000)
    SANDBOX_MODE: bool = _get_bool("SANDBOX_MODE", True)
```

> `python-dotenv` 在模块加载时调用 `load_dotenv()`，把项目 `.env` 中的配置加入进程环境。`Settings` 再将字符串转换为项目需要的类型。
>
> 当前 `settings = Settings()` 在导入模块时创建，因此修改 `.env` 后通常需要重启后端进程，已经运行的 Python 进程不会自动重新创建 Settings。

## 2.11 启动顺序

### 2.11.1 初始化数据

```bash
python -m database.seed_data
```

> 该命令会重建配置数据库中的演示数据。只应对本地学习数据库执行，不要让 `.env` 指向包含真实业务数据的数据库。第三章会解释种子脚本的删除和重建行为。

### 2.11.2 启动后端

```bash
cd backend
uvicorn app.main:app --reload
```

### 2.11.3 启动前端

```bash
cd frontend
npm run dev
```

> 后端默认监听 8000 端口，前端开发服务器默认使用 3000 端口。Vite 会把 `/api` 请求代理到后端。

## 2.12 代码地图

| 主题 | 文件 |
|---|---|
| Python 后端依赖 | `backend/requirements.txt` |
| 前端依赖和脚本 | `frontend/package.json` |
| 示例环境变量 | `.env.example` |
| 配置解析 | `backend/app/config.py` |
| FastAPI 生命周期 | `backend/app/main.py` |
| Agent 状态类型 | `backend/app/agents/state.py` |

## 2.13 动手验证

### 2.13.1 检查 Python 与关键依赖

```bash
python --version
python -c "import fastapi, duckdb, sqlglot, langgraph; print('backend dependencies OK')"
```

### 2.13.2 检查 Settings

```bash
cd backend
python -c "from app.config import settings; print(settings.APP_PORT, settings.DATABASE_URL, settings.SANDBOX_MODE)"
```

> 输出应包含端口、数据库 URL 和沙箱开关。不要在检查命令中打印 `QWEN_API_KEY`、JWT Secret 或数据库密码。

### 2.13.3 检查 Node.js 和前端依赖

```bash
node --version
npm --version
npm run build --prefix frontend
```

> 生产构建成功说明 Node.js、npm、Vue 源码和 Vite 构建链能够协作。构建不需要真实 LLM。

## 2.14 常见错误

### 2.14.1 PowerShell 禁止激活脚本

```text
running scripts is disabled on this system
```

> 这是 PowerShell 执行策略问题，不是 Python 代码错误。可以在当前用户范围调整策略，或者使用 Conda 环境和直接调用 `.venv\Scripts\python.exe`。修改企业设备策略前应遵守组织规定。

### 2.14.2 `pip` 和 `python` 不属于同一环境

> 使用 `python -m pip --version` 和 `python -c "import sys; print(sys.executable)"` 比较路径。推荐用 `python -m pip install`，让安装动作明确绑定当前解释器。

### 2.14.3 修改 `.env` 后行为没有变化

> 重启后端。Settings 在模块导入时创建，已经运行的进程不会自动重新加载新的环境变量。

### 2.14.4 后端启动但前端请求失败

> 依次检查后端端口、前端代理、CORS 来源和浏览器网络面板。不要先修改业务代码；很多连接失败只是端口或来源配置不一致。

### 2.14.5 LLM 调用失败

> 健康检查通过不代表模型端点可访问。分别确认 API Key 是否配置、URL 是否是 Chat Completions 兼容地址、模型名是否有效、网络是否允许访问。不要把完整响应或请求头粘贴进公开日志。

## 2.15 本章小结

> 项目运行环境由 Python、Node.js、依赖、数据库和环境变量共同构成。工作目录决定导入路径，虚拟环境决定使用哪组 Python 包，`.env` 决定程序连接哪些外部资源和采用哪些安全边界。
>
> 类型标注帮助理解接口，Pydantic负责运行时数据校验，TypedDict描述 LangGraph 共享状态，`async/await` 用于非阻塞地等待 I/O。这些知识已经足够开始阅读当前项目。

## 2.16 练习

> 1. 输出当前 Python 可执行文件路径和 pip 安装位置，确认它们属于同一环境；
> 2. 在不打印 Secret 的前提下，输出当前模型名和数据库后端；
> 3. 把 `APP_PORT` 临时设置为一个非数字值，观察配置导入错误，然后恢复正确值；
> 4. 找出 `package.json` 中开发、测试、构建和 E2E 四类命令；
> 5. 解释为什么修改 `.env` 后需要重启后端。

## 2.17 下一章衔接

> 环境准备完成后，下一章会学习项目最重要的事实来源：电商数据库。你将理解八张表、主外键、JOIN、聚合指标和种子数据，为后续 Schema Loader 和 SQL Generator 建立共同语言。

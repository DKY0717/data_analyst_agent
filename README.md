# Data Analyst Agent

自然语言驱动的数据库分析与 SQL 优化系统。用中文提问，系统自动生成安全 SQL、执行查询、修复错误，并返回自然语言解释和图表。

## 核心功能

- **自然语言转 SQL** — 用户提问，LLM 生成 DuckDB SQL
- **SQL 安全校验** — SQLGlot AST 解析，只允许 SELECT/WITH，自动注入 LIMIT
- **SQL 自动修复** — 执行失败时 LLM 分析错误并修复，最多重试 3 次
- **自然语言答案** — LLM 将查询结果转换为易懂的解释
- **数据可视化** — ECharts 自动选择图表类型
- **三栏工作台** — 输入/结果/SQL 详情一目了然

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Vue 3 + Vite + Element Plus + Pinia + ECharts |
| 后端 | FastAPI + LangGraph + SQLGlot |
| 数据库 | DuckDB |
| LLM | Qwen API (DashScope) |

## 快速开始

### 方式一：Docker（推荐）

```bash
# 1. 克隆项目
git clone <repo-url>
cd data_analyst_agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 QWEN_API_KEY

# 3. 一键启动
docker-compose up -d

# 4. 访问
# 前端: http://localhost
# API 文档: http://localhost:8000/docs
```

### 方式二：本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
python ../database/seed_data.py    # 初始化数据库
uvicorn app.main:app --reload      # 启动后端 (localhost:8000)

# 前端（新终端）
cd frontend
npm install
npm run dev                        # 启动前端 (localhost:3000)
```

## 示例问题

- 统计 2024 年每个月的订单数量
- 找出销售额最高的 5 个商品
- 统计各地区的客户数量
- 分析各商品类别的退款率

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/schema` | 数据库 Schema |
| POST | `/api/chat/query` | 自然语言查询 |

### 查询示例

```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "统计订单总数"}'
```

## 项目结构

```
data_analyst_agent/
├── backend/
│   ├── app/
│   │   ├── api/           # API 端点
│   │   ├── agents/        # LangGraph Agent 工作流
│   │   ├── db/            # 数据库连接和 Schema 加载
│   │   ├── security/      # SQL 安全校验
│   │   ├── services/      # LLM 服务
│   │   ├── models/        # Pydantic 模型
│   │   └── utils/         # 日志和异常
│   └── tests/             # 测试用例
├── frontend/
│   ├── src/
│   │   ├── api/           # API 客户端
│   │   ├── components/    # Vue 组件
│   │   ├── stores/        # Pinia 状态
│   │   └── views/         # 页面视图
│   └── nginx.conf         # Nginx 配置
├── database/
│   ├── init.sql           # 数据库 Schema
│   └── seed_data.py       # 种子数据脚本
├── docker-compose.yml     # Docker 编排
└── docs/                  # 项目文档
```

## 运行测试

```bash
cd backend
pytest -v
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QWEN_API_KEY` | DashScope API Key | 必填 |
| `QWEN_MODEL` | Qwen 模型名 | `qwen-turbo` |
| `SQL_TIMEOUT` | 查询超时（秒） | `30` |
| `SQL_MAX_ROWS` | 最大返回行数 | `1000` |
| `SQL_MAX_RETRIES` | SQL 修复最大重试 | `3` |

## License

MIT

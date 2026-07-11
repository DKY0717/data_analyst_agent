# 从零学习 Data Analyst Agent

> 这是一套面向初学者的中文项目课程。我们会从数据库、HTTP 和 Python 基础出发，逐步理解并复现自然语言分析、SQL 生成、安全校验、Agent 工作流、权限治理、前端工作台、自动化测试和部署。
>
> **课程状态：已完成（19/19）**
>
> **教学基线：** `4d71b3ce84cffe175fffaffa252a9072d6e79d18`
>
> **最后核对日期：** 2026-07-11

## 1. 为什么要做这套课程

> 当前项目已经能够接收中文或英文分析问题，生成 DuckDB SQL，经过安全和权限检查后执行查询，并把结果转换为自然语言答案、表格和图表。
>
> 仅仅把项目运行起来，并不等于理解项目。真正的理解意味着你能够说明每个模块为什么存在、输入输出是什么、失败后会走到哪里，以及修改某段代码后系统行为为什么会变化。
>
> 因此，这套课程不会按源码目录机械地逐文件介绍，而会按照系统从简单到完整的演进顺序展开。每一章都把概念、真实代码、执行流程和验证证据连接起来。

## 2. 这套课程适合谁

> 课程主要面向以下读者：
>
> - 使用 AI 编程完成了项目，希望真正掌握代码的人；
> - 了解少量 Python 或 SQL，但没有完成过 AI Agent 项目的人；
> - 希望准备毕业设计、作品集或 AI 应用工程岗位的人；
> - 希望基于当前项目继续开发和维护的人。
>
> 课程会补充理解项目必需的基础知识，但不会替代一门完整的 Python、数据库或 Vue 入门课程。遇到新概念时，先掌握它在当前项目中的作用，再决定是否继续扩展学习。

## 3. 学完后你能够做到什么

> 完成课程后，你应该能够：
>
> 1. 画出用户问题从前端进入数据库再返回答案的完整路径；
> 2. 解释为什么不能直接执行大模型生成的 SQL；
> 3. 理解规则解析、LLM 解析、语义层和 Schema Grounding 的关系；
> 4. 阅读并修改 LangGraph 的状态、节点和条件边；
> 5. 解释 SQL 自动修复为什么必须重新经过安全和权限检查；
> 6. 理解 JWT、API Key、表列权限和行级过滤的不同职责；
> 7. 阅读 Vue、Pinia、Axios、SSE 和 ECharts 组成的前端工作台；
> 8. 使用单元测试、端到端测试和结构化评测验证系统；
> 9. 使用 Docker Compose 启动完整项目；
> 10. 在干净环境中复现核心业务路径和安全失败路径。

## 4. 课程结构

> 课程参考系统性在线教材的组织方式，分为五个部分、十九章。每章是一个独立 Markdown 页面，章内继续使用编号小节拆分知识点。

| 部分 | 章节 | 核心问题 | 当前状态 |
|---|---|---|---|
| 第一部分：基础准备 | [第1章 认识 Data Analyst Agent](part01-foundations/chapter01-project-overview.md) | 项目解决什么问题，完整链路是什么 | 已完成 |
|  | [第2章 开发环境与必备 Python 基础](part01-foundations/chapter02-development-environment-and-python.md) | 如何准备并理解项目运行环境 | 已完成 |
|  | [第3章 数据库、SQL 与电商业务模型](part01-foundations/chapter03-database-sql-and-domain-model.md) | 八张业务表如何支撑分析问题 | 已完成 |
| 第二部分：最小可用系统 | [第4章 初始化数据库与加载 Schema](part02-minimum-system/chapter04-database-init-and-schema.md) | 程序如何认识数据库 | 已完成 |
|  | [第5章 搭建 FastAPI 后端](part02-minimum-system/chapter05-fastapi-backend.md) | HTTP 请求如何进入 Python 业务逻辑 | 已完成 |
|  | [第6章 接入 OpenAI-compatible 大模型](part02-minimum-system/chapter06-openai-compatible-llm.md) | 如何安全、稳定地调用 LLM | 已完成 |
|  | [第7章 第一条自然语言转 SQL 链路](part02-minimum-system/chapter07-first-nl2sql-pipeline.md) | 如何完成最小 NL2SQL 闭环 | 已完成 |
| 第三部分：完整 Agent 工作流 | [第8章 SQL 安全防护](part03-agent-workflow/chapter08-sql-safety.md) | 如何阻止危险意图和危险 SQL | 已完成 |
|  | [第9章 结构化分析意图](part03-agent-workflow/chapter09-analysis-intent.md) | 如何识别指标、维度和筛选条件 | 已完成 |
|  | [第10章 语义层、Grounding 与澄清](part03-agent-workflow/chapter10-semantic-grounding-clarification.md) | 业务概念如何落到真实表字段 | 已完成 |
|  | [第11章 LangGraph 工作流](part03-agent-workflow/chapter11-langgraph-workflow.md) | 节点、状态和分支如何协作 | 已完成 |
|  | [第12章 修复、优化与多轮分析](part03-agent-workflow/chapter12-repair-optimization-multiturn.md) | 系统如何从失败中恢复并继承上下文 | 已完成 |
| 第四部分：完整产品 | [第13章 认证、权限与安全审计](part04-productization/chapter13-auth-permission-audit.md) | 谁可以查询什么数据 | 已完成 |
|  | [第14章 SSE、缓存与可观测性](part04-productization/chapter14-sse-cache-observability.md) | 如何改善体验并观察系统成本 | 已完成 |
|  | [第15章 Vue 数据分析工作台](part04-productization/chapter15-vue-workbench.md) | 后端能力如何成为可交互产品 | 已完成 |
| 第五部分：质量与毕业设计 | [第16章 自动化测试](part05-quality-and-graduation/chapter16-automated-testing.md) | 如何证明关键代码没有回归 | 已完成 |
|  | [第17章 评测体系与质量门禁](part05-quality-and-graduation/chapter17-evaluation-and-quality-gate.md) | 如何衡量 NL2SQL 是否可靠 | 已完成 |
|  | [第18章 Docker、Nginx 与 CI](part05-quality-and-graduation/chapter18-docker-nginx-ci.md) | 如何交付和持续验证项目 | 已完成 |
|  | [第19章 完整复现与项目复盘](part05-quality-and-graduation/chapter19-reproduction-and-roadmap.md) | 如何独立走通项目并继续优化 | 已完成 |

## 5. 每章怎么学习

> 推荐按照章节顺序学习。每章都包含固定的学习闭环：

```text
明确本章目标
  → 理解问题场景和基础概念
  → 查看真实代码地图
  → 阅读关键实现和执行流程
  → 运行验收命令
  → 分析常见错误
  → 完成练习并进入下一章
```

> 阅读代码时不要追求一次记住所有细节。先回答“输入是什么、输出是什么、为什么需要它、失败会怎样”，再进入函数内部理解实现。

## 6. 三种验证方式

### 6.1 确定性验证

> 这类验证不调用真实 LLM，通常使用 pytest、固定数据或 Mock。它适合学习代码结构、安全规则、权限行为和异常分支，也是日常开发最稳定的反馈方式。

```bash
pytest backend/tests/test_health.py -q
```

### 6.2 本地完整运行

> 这类验证会启动后端和前端，并可能调用你配置的 OpenAI-compatible LLM。它最接近真实用户体验，但需要有效的 API Key、可访问的模型地址和本地数据库。

```bash
# 终端一：启动后端
cd backend
uvicorn app.main:app --reload

# 终端二：启动前端
cd frontend
npm run dev
```

### 6.3 Docker 验证

> Docker 路线用于检查镜像、容器网络、Nginx 代理、持久化数据和健康检查能否组成完整交付环境。

```bash
docker compose up -d --build
```

## 7. LLM 费用与安全提示

> 真实模型调用可能产生费用。课程会优先提供确定性测试，只有在验证真实模型行为时才要求配置 API Key。
>
> 不要把 API Key、JWT Secret 或数据库密码写进 Markdown、代码、截图、终端记录或 Git 提交。项目保留 `QWEN_*` 环境变量名称以兼容历史配置，但可以连接 MiMo、Qwen 或其他 OpenAI-compatible 服务，具体能力以当前 `.env.example` 和 `backend/app/config.py` 为准。

## 8. 课程与源码的关系

> 当前仓库源码是唯一实现事实来源。课程不会复制十九份完整项目快照，而会在每章提供“代码地图”，指向对应源码、测试和验收命令。
>
> [代码与章节映射](CODE-MAP.md) 用于快速定位学习内容；[更新日志](CHANGELOG.md) 用于记录项目升级后哪些章节发生变化。

## 9. 推荐学习节奏

| 阶段 | 推荐节奏 | 阶段成果 |
|---|---|---|
| 第一部分 | 2～4 天 | 能运行项目并读懂数据库关系 |
| 第二部分 | 4～7 天 | 理解最小 NL2SQL 请求闭环 |
| 第三部分 | 7～14 天 | 理解完整 Agent、安全和修复流程 |
| 第四部分 | 5～8 天 | 能解释权限、可观测性和前端工作台 |
| 第五部分 | 4～7 天 | 能测试、评测、部署并独立复现项目 |

> 学习时间只是参考。是否真正完成一章，应以能否运行验证、解释结果和完成练习为准，而不是阅读时长。

## 10. 版本维护

> 第一版课程对应教学基线提交 `4d71b3c`。项目后续优化时，先更新 `CODE-MAP.md` 中受影响的源码和测试，再修订对应章节，最后在 `CHANGELOG.md` 中记录行为变化和验证结果。
>
> 如果课程文字与当前代码冲突，应以当前代码、测试和实际运行证据为准，并把差异记录为需要修订的文档问题。

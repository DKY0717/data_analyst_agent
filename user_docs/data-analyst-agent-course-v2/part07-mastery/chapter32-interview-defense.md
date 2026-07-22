# 第32章 面试演示与项目答辩

> 本章预计 1～2 小时准备，并建议至少录屏演练两次。目标不是背诵漂亮话，而是把每个技术判断绑定到可现场验证的代码、测试或历史证据。

## 32.1 学习目标

> 完成本章后，你应该能够：
>
> - 完成 30 秒、5 分钟和 10 分钟三档介绍；
> - 画出主链路并解释三个条件分支；
> - 演示正常查询、权限对照和安全阻断；
> - 准确复盘 MiMo 不完整真实评测；
> - 诚实回答“项目是不是 AI 写的、你个人做了什么”；
> - 用评分表识别自己仍然讲不清的部分。

## 32.2 前置知识

> 你已经完成课程练习，至少亲手做过一次指标设计、一次故障定位和一次 Mini Agent 重建。若这三项尚未完成，不建议把“独立开发”写进简历。

## 32.3 为什么需要这一模块

> 面试官关心的不是仓库有多少文件，而是你能否解释需求、架构、安全边界、失败处理、证据与取舍。Vibe coding 并不会自动让项目失去价值，真正风险是你声称独立实现所有代码，却无法解释关键控制流。
>
> 最可信的表达是：项目采用 AI 辅助迭代，你负责目标与约束、方案选择、代码审查、测试验收、事故分析和后续重建学习；然后用现场调试与 Mini Agent 证明理解已经从“生成代码”转化为个人能力。

## 32.4 输入、输出与依赖

### 面试输入包

> - 当前 HEAD 与干净的演示分支；
> - 本地确定性测试结果；
> - 前端构建和预检结果；
> - 真实 run `29634864907` 的脱敏事实；
> - 一份失败降级材料：架构图、测试报告、课程代码地图；
> - 你个人 Mini Agent 的独立仓库与提交历史。

### 输出

> 输出是三档讲解、一个可恢复演示、三个 STAR 故事、问题库回答和一份证据索引。不要以现场真实模型一次成功作为唯一输出。

## 32.5 执行流程

```text
核对当前 HEAD 与证据日期
  → 运行本地预检
  → 选择 3 条稳定演示路径
  → 准备网络/模型失败降级材料
  → 录制 10 分钟演示
  → 按评分表复盘
  → 删除无法举证和过度承诺的话
  → 模拟追问与现场调试
```

> 面试前一天冻结演示版本。临时升级依赖、修改 Prompt 或更换 Key 都会引入不必要风险。

## 32.6 当前代码地图

| 内容 | 路径 | 使用方式 |
|---|---|---|
| 演示预检 | `scripts/interview_demo_preflight.py` | 检查文件、配置、readiness、前端 |
| 证据清单生成 | `scripts/interview_evidence.py` | 生成命令清单，不会替你验证证据 |
| 面试讲述稿 | `docs/interview_guide.md` | 参考后必须与当前 HEAD 核对数字 |
| 简历包装包 | `docs/resume_project_packet.md` | 候选表达，不是自动可信事实 |
| 学习检查 | `user_docs/data-analyst-agent-course-v2/STUDY-CHECKLIST.md` | 逐项自评 |
| 问题库 | `user_docs/data-analyst-agent-course-v2/INTERVIEW-QUESTIONS.md` | 模拟追问 |
| 当前代码地图 | `user_docs/data-analyst-agent-course-v2/CURRENT-CODE-MAP.md` | 现场从问题跳到源码 |
| 事故复盘 | `user_docs/data-analyst-agent-course-v2/part06-quality/chapter28-mimo-timeout-incident.md` | 如实说明失败证据 |

> `interview_evidence.py` 只是生成 Markdown 命令清单，不联网、不下载、不验证 Artifact 完整性；其中 Artifact 名称还必须与当前 workflow 实际产物核对。脚本输出不能自动证明真实评测通过。

## 32.7 关键代码理解

### 30 秒介绍

> 可以按下面结构练习，但要换成自己的语言：
>
> “这是一个面向电商分析的 NL2SQL Agent。它把自然语言问题解析成业务 Intent，经过 Schema Grounding 生成 DuckDB SQL，并在执行前通过 Intent Guard、SQLGlot SQL Guard 和角色数据权限三层治理。执行失败可以 Repair，结果有审计、图表和专项评测。项目重点不是让模型写 SQL，而是让不稳定模型输出进入可控、可测试、可审计的工程闭环。”

> 不要在 30 秒里堆所有库名。先说问题、闭环和一个差异化亮点，让面试官决定追问方向。

### 5 分钟架构讲解

| 时间 | 内容 | 必须讲清的证据 |
|---:|---|---|
| 0:00～0:40 | 场景与风险 | 自然语言歧义、危险 SQL、业务口径 |
| 0:40～2:00 | 主链路 | Intent → Grounding → Generate → Guard → Execute |
| 2:00～3:00 | 三个分支 | 澄清暂停、权限阻断、Repair 循环 |
| 3:00～4:00 | 产品化 | FastAPI/SSE、Vue、审计、部署 |
| 4:00～5:00 | 质量证据 | 分层评测、分片、严格汇总、事故边界 |

> 白板图至少画出：危险意图在 LLM 前终止；修复 SQL重新经过 SQL Guard 和 Permission Guard；只有执行成功才进入答案生成。能画条件边比背“12 节点”更重要。

### 10 分钟演示

```text
0:00～1:00  项目定位与当前 HEAD
1:00～3:00  正常分析问题：Intent/Grounding/SQL/结果/图表
3:00～5:00  analyst 行过滤与 admin 对照
5:00～6:30  危险意图或敏感列阻断
6:30～8:00  展示测试/评测与严格证据机制
8:00～9:00  MiMo 超时事故：8/13、3/3、5/5、门禁 skipped
9:00～10:00  个人贡献、Mini Agent 与下一步改进
```

> 建议演示问题固定为三个：一条按月销售额、一条 analyst 敏感列拒绝并用 admin 对照、一条删除表危险意图。不要现场随机问复杂问题证明“智能”。

### 三个 STAR 故事

> **安全闭环：** 说明 Prompt 约束不可信，因此在执行前增加 Intent/SQL/Permission 三层确定性治理，阻断不进入 DB/Repair，并用 rule ID、审计和测试证明。
>
> **结果正确性：** 说明可执行 SQL 仍可能 JOIN 重复或口径错误，因此增加黄金 SQL、结果比较、排序/容差/固定断言，不把执行率包装成准确率。
>
> **真实模型事故：** 说明空 content 与客户端无界重试路径叠加，5 个 NL2SQL 分片触达 75 分钟；严格汇总拒绝残缺报告，阈值 step skipped。提出统一重试预算和 case deadline。

### 如何回答“这是 AI 写的吗”

> 推荐诚实回答：
>
> “项目早期大量使用 AI 辅助生成和迭代，所以我不会声称每行都是手写。我的工作重点是定义需求和安全约束、审查方案、组织测试与评测、复盘真实运行，并通过这套课程重新逐层学习。为了验证已经掌握，我还在独立仓库从零重建了不依赖 LangGraph 的 Mini Agent，并能现场解释或修改关键链路。”

> 若你尚未完成 Mini Agent，就删除最后一句。诚信比包装更重要；面试官通常会通过追问快速判断。

### 如何描述真实评测

> 准确说法：目标 SHA 的 preflight 成功；NL2SQL 8/13 分片成功、5 个超时；Repair 3/3、correctness 5/5 job 成功；NL2SQL 严格汇总失败，阈值门禁 skipped。它证明证据机制能 fail closed，也暴露了当前 LLM 重试缺陷；不能说真实模型全量通过。

## 32.8 最小动手运行

> 先运行脚本单测，证明预检与证据清单的稳定行为。

```powershell
pytest backend/tests/test_interview_demo_preflight_script.py backend/tests/test_interview_evidence_script.py -q
```

> 服务未启动时可以先跳过网络检查，读取预检报告；不要加 `--strict` 后把预期配置缺失误判成脚本 bug。

```powershell
python scripts/interview_demo_preflight.py --no-network
python scripts/interview_evidence.py --run-id 29634864907
```

> 正式演示前启动后端/前端并使用严格预检。脚本会隐藏 JWT_SECRET 的值，但你仍不应把 `.env` 或终端密钥画面共享给面试官。

```powershell
python scripts/interview_demo_preflight.py --strict
```

## 32.9 故障注入实验

> 演示前关闭本地后端或使用 `--no-network` 模拟无法连服务，练习在 30 秒内切换到离线材料：架构图、SQL Guard 测试、权限 evaluator、历史脱敏 run。
>
> 再假设真实模型当场返回空 content。正确操作是说明已有事故边界并切换 Fake LLM/历史证据，不要反复点击、暴露 Key 或现场修改重试循环。
>
> 最后让同伴随机问一个你不确定的测试数字。正确回答是现场运行/查报告或说“我需要核对当前 HEAD”，不是背旧文档中的历史数字。

## 32.10 调试路径与常见误判

> 演示失败先判断服务/端口、认证配置、数据库 readiness、前端代理、模型网络，再切降级材料。不要在面试现场执行依赖安装或数据库重建。
>
> 常见误判一：仓库功能多就能证明能力。面试官更看重你能否解释两三个关键取舍。
>
> 常见误判二：引用 `docs/interview_guide.md` 中的数字就算证据。项目持续变化，任何测试数量和评测结果都要在当前 HEAD 重新核对。
>
> 常见误判三：现场模型成功一次就是可靠性证明。可靠性来自确定性测试、固定 case、身份完整和可审计报告。
>
> 常见误判四：隐藏 AI 辅助经历。更好的做法是明确 AI 的作用，并用独立重建、调试和代码审查展示个人掌握。
>
> 常见误判五：把门禁 job failure 说成阈值不达标。本次 run 的阈值 step 没有执行。

## 32.11 独立编码练习

> 录制一遍完整 10 分钟演示，并用下面规则删稿：没有代码/测试/报告支持的句子删掉；无法解释分母的百分比删掉；“完全、绝对、生产级、100%安全”等过度词删掉。

> 再准备四个高频追问：
>
> 1. 为什么要 LangGraph，而不是一个函数？
> 2. 怎么保证危险 SQL和越权数据不会执行？
> 3. SQL 执行成功为什么还不等于正确？
> 4. 项目是 AI 辅助的，你个人真正掌握了什么？

> 每个回答控制在 60～90 秒，并至少指出一个源码路径和一类验证证据。

## 32.12 测试或评测验证

> 面试前最低离线检查：课程契约、预检脚本测试、关键安全/权限/Graph 测试、前端测试和构建。按当前 HEAD 记录实际数量，不提前写死。

```powershell
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_interview_demo_preflight_script.py backend/tests/test_interview_evidence_script.py backend/tests/test_sql_guard.py backend/tests/test_data_permission_guard.py backend/tests/test_agent_graph.py -q
npm run test --prefix frontend
npm run build --prefix frontend
```

> 如果使用远端证据，必须检查 run HEAD、provider/model、所有分片与严格汇总。Run `29634864907` 只能作为事故复盘，不能作为当前 HEAD 全量通过证明。

### 自评量表

| 维度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| 项目定位 | 只说“LLM写SQL” | 能说功能 | 能说风险与工程闭环 |
| 架构 | 背库名 | 能画主链路 | 能解释条件边和状态 |
| 安全 | 只说 Prompt | 知道 SQL Guard | 能讲 Intent/SQL/Permission 与短路证据 |
| 正确性 | 只看执行 | 知道黄金 SQL | 能讲粒度、顺序、容差、固定断言 |
| 调试 | 随机改 Prompt | 有排查顺序 | 能给最小复现、边界证据和回归 |
| 真实评测 | 说“大部分通过” | 记得分片数 | 能说门禁 skipped 与证据边界 |
| 个人贡献 | 回避 AI | 承认 AI 辅助 | 有独立重建与提交证据 |
| 现场恢复 | 服务挂了就停 | 有截图 | 能切离线测试/报告并继续讲 |

> 满分 16 分。达到 13 分且任何单项不为 0，才建议把项目作为主面试项目；否则回到对应章节补练。

## 32.13 面试复述题

> **问题：你在这个项目中最重要的三个工程判断是什么？**
>
> 一种合格结构：第一，不信任模型输出，用三层 Guard和权限短路；第二，不把执行成功当结果正确，用黄金 SQL 与比较器；第三，不把残缺真实评测当成绩，用 checkpoint、严格汇总和 fail closed。每一点都给源码与测试/运行证据。
>
> **追问：这个项目现在最大的已知问题是什么？**
>
> 应回答：真实 MiMo 运行暴露空 content 分支缺少有效内部终止，5 个 NL2SQL 分片依赖 75 分钟外层超时；当前不能宣称完整真实模型门禁通过。下一步应修统一重试预算与 case deadline，补确定性回归，再重跑完整评测。

## 32.14 掌握度检查与下一章

> 当你能不看稿画架构、准确解释 run `29634864907`、现场定位一个故障、从零重建 Mini Agent，并诚实说明 AI 辅助与个人贡献，这门课程才算完成。
>
> 后续不再盲目增加章节。每次项目变更都从 `CURRENT-CODE-MAP.md` 找受影响模块，更新正文、练习、验证和 `CHANGELOG.md`，让课程始终跟随可验证的当前代码。
